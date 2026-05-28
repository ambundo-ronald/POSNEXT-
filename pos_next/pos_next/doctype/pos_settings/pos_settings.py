# Copyright (c) 2025, Youssef Restom and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt, get_url

GLOBAL_SETTINGS_DOCTYPE = "POS Next Global Settings"
SMS_ENABLER_FIELDS = {
	"sms_enabler_enabled",
	"sms_enabler_source",
	"sms_enabler_token",
	"sms_enabler_sender_mappings",
}


class POSSettings(Document):
	def validate(self):
		"""Validate POS Settings"""
		# Guard against None values and validate discount percentage
		max_discount = flt(self.max_discount_allowed)
		if max_discount < 0 or max_discount > 100:
			frappe.throw("Max Discount Allowed must be between 0 and 100")

		# Guard against None values and validate search limit
		if self.use_limit_search:
			search_limit = cint(self.search_limit)
			if search_limit <= 0:
				frappe.throw("Search Limit must be greater than 0")

		if self.sms_payment_reconciliation_mode not in ("Manual", "Suggested", "Auto"):
			frappe.throw("SMS Payment Reconciliation must be Manual, Suggested, or Auto")

		seen_credit_users = set()
		for row in self.get("credit_sale_users") or []:
			if not row.get("user"):
				frappe.throw("Credit sale user is required")
			if row.user in seen_credit_users:
				frappe.throw(f"Duplicate credit sale user: {row.user}")
			seen_credit_users.add(row.user)

	def on_update(self):
		"""Sync allow_negative_stock with Stock Settings"""
		self.sync_negative_stock_setting()

	def sync_negative_stock_setting(self):
		"""
		Synchronize allow_negative_stock with Stock Settings.

		When enabled in POS Settings, it enables the global Stock Settings.
		When disabled, it only disables global Stock Settings if no other
		POS Settings have it enabled.

		Note: Runs in the same transaction as the save, no manual commits.
		"""
		current_stock_setting = cint(
			frappe.db.get_single_value("Stock Settings", "allow_negative_stock") or 0
		)

		if cint(self.allow_negative_stock):
			# Enable Stock Settings if not already enabled
			if not current_stock_setting:
				frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1, update_modified=False)
				frappe.msgprint(
					"Stock Settings 'Allow Negative Stock' has been automatically enabled.",
					indicator="green",
					alert=True
				)
		else:
			# Only disable if no other enabled POS Settings have it enabled
			if current_stock_setting:
				# Use count for better performance and clarity
				other_enabled_count = frappe.db.count(
					"POS Settings",
					{
						"allow_negative_stock": 1,
						"enabled": 1,  # Only check enabled POS Settings
						"name": ["!=", self.name]
					}
				)

				if other_enabled_count == 0:
					frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 0, update_modified=False)
					frappe.msgprint(
						"Stock Settings 'Allow Negative Stock' has been automatically disabled.",
						indicator="orange",
						alert=True
					)


def get_sms_enabler_webhook_url():
	"""Return the single public SMS Enabler webhook URL for this site."""
	return get_url("/api/method/pos_next.api.smsenabler_mpesa.receive_sms")


def _serialize_sms_sender_mappings(doc):
	return [
		{
			"enabled": cint(row.get("enabled")),
			"match_text": row.get("match_text") or "",
			"mode_of_payment": row.get("mode_of_payment") or "",
		}
		for row in doc.get("sms_enabler_sender_mappings") or []
	]


def _serialize_credit_sale_users(doc):
	return [
		{
			"enabled": cint(row.get("enabled")),
			"user": row.get("user") or "",
			"full_name": row.get("full_name") or frappe.db.get_value("User", row.get("user"), "full_name") or "",
		}
		for row in doc.get("credit_sale_users") or []
	]


def _inject_credit_sale_access(settings):
	settings["current_user"] = frappe.session.user

	pos_settings_name = settings.get("name")
	if pos_settings_name:
		try:
			doc = frappe.get_doc("POS Settings", pos_settings_name)
			settings["credit_sale_users"] = _serialize_credit_sale_users(doc)
		except Exception:
			settings["credit_sale_users"] = []
	else:
		settings["credit_sale_users"] = []

	settings["credit_sale_allowed_for_user"] = is_credit_sale_allowed_for_user(
		settings.get("pos_profile"),
		user=frappe.session.user,
		settings=settings,
	)
	return settings


def get_profile_allow_edit_rate(pos_profile):
	"""Return the standard POS Profile edit-rate flag when available."""
	if not pos_profile:
		return 0

	try:
		if not frappe.get_meta("POS Profile").has_field("allow_user_to_edit_rate"):
			return 0
		return cint(frappe.db.get_value("POS Profile", pos_profile, "allow_user_to_edit_rate") or 0)
	except Exception:
		return 0


def is_credit_sale_allowed_for_user(pos_profile, user=None, settings=None):
	user = user or frappe.session.user
	if not pos_profile:
		return False

	if settings is None:
		settings = frappe.db.get_value(
			"POS Settings",
			{"pos_profile": pos_profile, "enabled": 1},
			["name", "allow_credit_sale", "pos_profile"],
			as_dict=True,
		)

	if not settings or not cint(settings.get("allow_credit_sale")):
		return False

	credit_sale_users = settings.get("credit_sale_users")
	if credit_sale_users is None:
		pos_settings_name = settings.get("name")
		if not pos_settings_name:
			pos_settings_name = frappe.db.get_value(
				"POS Settings",
				{"pos_profile": pos_profile, "enabled": 1},
				"name",
			)

		if pos_settings_name:
			credit_sale_users = frappe.get_all(
				"POS Credit Sale User",
				filters={"parent": pos_settings_name, "enabled": 1},
				fields=["user"],
			)
		else:
			credit_sale_users = []

	allowed_users = [row.get("user") for row in credit_sale_users or [] if cint(row.get("enabled", 1)) and row.get("user")]

	# Backward compatibility: if no users are configured, the profile-level
	# toggle keeps its old behavior and all assigned POS users may sell on credit.
	if not allowed_users:
		return True

	return user in allowed_users


def _get_legacy_sms_enabler_settings():
	"""Return one existing profile-level SMS Enabler config for migration."""
	return frappe.db.get_value(
		"POS Settings",
		{"enabled": 1, "sms_enabler_enabled": 1},
		["sms_enabler_enabled", "sms_enabler_source", "sms_enabler_token"],
		as_dict=True,
		order_by="modified desc",
	)


def get_global_sms_enabler_settings(create=False):
	"""Get the site-wide SMS Enabler settings, migrating old profile config once."""
	try:
		doc = frappe.get_single(GLOBAL_SETTINGS_DOCTYPE)
	except Exception:
		return {
			"sms_enabler_enabled": 0,
			"sms_enabler_source": "SMS Enabler",
			"sms_enabler_token": "",
			"sms_enabler_sender_mappings": [],
			"sms_enabler_webhook_url": get_sms_enabler_webhook_url(),
			"sms_enabler_is_global": 1,
		}

	if not doc.get("sms_enabler_token"):
		legacy = _get_legacy_sms_enabler_settings()
		if legacy:
			doc.sms_enabler_enabled = cint(legacy.get("sms_enabler_enabled"))
			doc.sms_enabler_source = legacy.get("sms_enabler_source") or "SMS Enabler"
			doc.sms_enabler_token = legacy.get("sms_enabler_token") or frappe.generate_hash(length=32)
			doc.save(ignore_permissions=True)
		elif create:
			doc.sms_enabler_source = doc.get("sms_enabler_source") or "SMS Enabler"
			doc.save(ignore_permissions=True)

	return {
		"sms_enabler_enabled": cint(doc.get("sms_enabler_enabled")),
		"sms_enabler_source": doc.get("sms_enabler_source") or "SMS Enabler",
		"sms_enabler_token": doc.get("sms_enabler_token") or "",
		"sms_enabler_sender_mappings": _serialize_sms_sender_mappings(doc),
		"sms_enabler_webhook_url": get_sms_enabler_webhook_url(),
		"sms_enabler_is_global": 1,
	}


def update_global_sms_enabler_settings(settings):
	"""Persist site-wide SMS Enabler fields from the POS Settings screen."""
	if not settings:
		return get_global_sms_enabler_settings()

	current = get_global_sms_enabler_settings()
	next_enabled = cint(settings.get("sms_enabler_enabled"))
	next_source = settings.get("sms_enabler_source") or "SMS Enabler"
	next_mappings = settings.get("sms_enabler_sender_mappings") or []

	if (
		next_enabled == cint(current.get("sms_enabler_enabled"))
		and next_source == (current.get("sms_enabler_source") or "SMS Enabler")
		and next_mappings == (current.get("sms_enabler_sender_mappings") or [])
	):
		return current

	if not frappe.has_permission(GLOBAL_SETTINGS_DOCTYPE, "write"):
		frappe.throw("You don't have permission to update site SMS Enabler settings")

	doc = frappe.get_single(GLOBAL_SETTINGS_DOCTYPE)
	doc.sms_enabler_enabled = next_enabled
	doc.sms_enabler_source = next_source
	doc.set("sms_enabler_sender_mappings", [])
	for mapping in next_mappings:
		match_text = (mapping.get("match_text") or "").strip()
		mode_of_payment = mapping.get("mode_of_payment")
		if isinstance(mode_of_payment, dict):
			mode_of_payment = mode_of_payment.get("value") or mode_of_payment.get("label")
		if not match_text and not mode_of_payment:
			continue
		doc.append(
			"sms_enabler_sender_mappings",
			{
				"enabled": cint(mapping.get("enabled", 1)),
				"match_text": match_text,
				"mode_of_payment": mode_of_payment,
			},
		)

	if cint(doc.sms_enabler_enabled) and not doc.get("sms_enabler_token"):
		doc.sms_enabler_token = frappe.generate_hash(length=32)

	doc.save()
	return get_global_sms_enabler_settings()


def _inject_global_sms_enabler_settings(settings):
	settings.update(get_global_sms_enabler_settings())
	_inject_credit_sale_access(settings)
	return settings


@frappe.whitelist()
def get_pos_settings(pos_profile):
	"""
	Get POS Settings for a specific POS Profile.

	Also injects the current global Stock Settings value to show the actual
	source of truth, preventing confusion when the checkbox appears enabled
	but the global setting was changed elsewhere.
	"""
	from frappe import _

	if not pos_profile:
		return None

	# Check if user has access to this POS Profile
	has_access = frappe.db.exists(
		"POS Profile User",
		{"parent": pos_profile, "user": frappe.session.user}
	)

	if not has_access and not frappe.has_permission("POS Settings", "read"):
		frappe.throw(_("You don't have access to this POS Profile"))

	settings = frappe.db.get_value(
		"POS Settings",
		{"pos_profile": pos_profile},
		"*",
		as_dict=True
	)

	# If no settings exist, create default settings
	if not settings:
		settings = create_default_settings(pos_profile)

	settings["allow_user_to_edit_rate"] = cint(settings.get("allow_user_to_edit_rate")) or get_profile_allow_edit_rate(pos_profile)

	# Inject the current global Stock Settings value for transparency
	# This helps UI reflect the actual state even if multiple POS Settings exist
	settings["_global_allow_negative_stock"] = cint(
		frappe.db.get_single_value("Stock Settings", "allow_negative_stock") or 0
	)
	_inject_global_sms_enabler_settings(settings)

	return settings


def create_default_settings(pos_profile):
	"""Create default POS Settings for a POS Profile"""
	doc = frappe.new_doc("POS Settings")
	doc.pos_profile = pos_profile
	doc.enabled = 1
	doc.sms_payment_reconciliation_mode = "Manual"
	doc.insert()

	settings = doc.as_dict()
	_inject_global_sms_enabler_settings(settings)
	return settings


@frappe.whitelist()
def update_pos_settings(pos_profile, settings):
	"""Update POS Settings for a POS Profile"""
	import json
	from frappe import _

	if isinstance(settings, str):
		settings = json.loads(settings)

	# Check if user has access to this POS Profile
	has_access = frappe.db.exists(
		"POS Profile User",
		{"parent": pos_profile, "user": frappe.session.user}
	)

	if not has_access and not frappe.has_permission("POS Settings", "write"):
		frappe.throw(_("You don't have permission to update this POS Profile"))

	update_global_sms_enabler_settings(settings)

	credit_sale_users = settings.get("credit_sale_users") or []

	# Remove transient values injected for the frontend.
	settings = {
		key: value
		for key, value in settings.items()
		if not key.startswith("_")
		and key not in {"sms_enabler_webhook_url", "sms_enabler_is_global", "current_user", "credit_sale_allowed_for_user"}
		and key not in SMS_ENABLER_FIELDS
		and key != "credit_sale_users"
	}

	# Check if settings exist
	existing = frappe.db.exists("POS Settings", {"pos_profile": pos_profile})

	if existing:
		doc = frappe.get_doc("POS Settings", existing)
		doc.update(settings)
		doc.set("credit_sale_users", [])
		for row in credit_sale_users:
			user = row.get("user")
			if isinstance(user, dict):
				user = user.get("value") or user.get("label")
			if not user:
				continue
			doc.append(
				"credit_sale_users",
				{
					"enabled": cint(row.get("enabled", 1)),
					"user": user,
				},
			)
		doc.save()
	else:
		doc = frappe.new_doc("POS Settings")
		doc.pos_profile = pos_profile
		doc.update(settings)
		for row in credit_sale_users:
			user = row.get("user")
			if isinstance(user, dict):
				user = user.get("value") or user.get("label")
			if not user:
				continue
			doc.append(
				"credit_sale_users",
				{
					"enabled": cint(row.get("enabled", 1)),
					"user": user,
				},
			)
		doc.insert()

	result = doc.as_dict()
	result["allow_user_to_edit_rate"] = cint(result.get("allow_user_to_edit_rate")) or get_profile_allow_edit_rate(pos_profile)
	_inject_global_sms_enabler_settings(result)
	return result


@frappe.whitelist()
def regenerate_sms_enabler_token(pos_profile=None):
	"""Rotate the site-wide SMS Enabler webhook token."""
	from frappe import _

	if not frappe.has_permission(GLOBAL_SETTINGS_DOCTYPE, "write"):
		frappe.throw(_("You don't have permission to update SMS Enabler settings"))

	doc = frappe.get_single(GLOBAL_SETTINGS_DOCTYPE)
	doc.sms_enabler_enabled = 1
	doc.sms_enabler_source = doc.get("sms_enabler_source") or "SMS Enabler"
	doc.sms_enabler_token = frappe.generate_hash(length=32)
	doc.save()

	return {
		"token": doc.sms_enabler_token,
		"webhook_url": get_sms_enabler_webhook_url(),
		"sms_enabler_is_global": 1,
	}

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

	if (
		next_enabled == cint(current.get("sms_enabler_enabled"))
		and next_source == (current.get("sms_enabler_source") or "SMS Enabler")
	):
		return current

	if not frappe.has_permission(GLOBAL_SETTINGS_DOCTYPE, "write"):
		frappe.throw("You don't have permission to update site SMS Enabler settings")

	doc = frappe.get_single(GLOBAL_SETTINGS_DOCTYPE)
	doc.sms_enabler_enabled = next_enabled
	doc.sms_enabler_source = next_source

	if cint(doc.sms_enabler_enabled) and not doc.get("sms_enabler_token"):
		doc.sms_enabler_token = frappe.generate_hash(length=32)

	doc.save()
	return get_global_sms_enabler_settings()


def _inject_global_sms_enabler_settings(settings):
	settings.update(get_global_sms_enabler_settings())
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

	# Remove transient values injected for the frontend.
	settings = {
		key: value
		for key, value in settings.items()
		if not key.startswith("_")
		and key not in {"sms_enabler_webhook_url", "sms_enabler_is_global"}
		and key not in SMS_ENABLER_FIELDS
	}

	# Check if settings exist
	existing = frappe.db.exists("POS Settings", {"pos_profile": pos_profile})

	if existing:
		doc = frappe.get_doc("POS Settings", existing)
		doc.update(settings)
		doc.save()
	else:
		doc = frappe.new_doc("POS Settings")
		doc.pos_profile = pos_profile
		doc.update(settings)
		doc.insert()

	result = doc.as_dict()
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

# -*- coding: utf-8 -*-
# Copyright (c) 2024, POS Next and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import json
import frappe
from frappe import _
from frappe.utils import nowdate, nowtime, get_datetime


def _is_cash_mode(mode_of_payment, pos_profile=None):
	"""The drawer-cash method: the POS Profile's cash mode, else the one named Cash."""
	if not mode_of_payment:
		return False
	cash_mode = (
		frappe.get_cached_value("POS Profile", pos_profile, "posa_cash_mode_of_payment")
		if pos_profile
		else None
	)
	if cash_mode:
		return mode_of_payment == cash_mode
	return mode_of_payment.strip().lower() == "cash"


def _require_cash_amounts(rows, amount_field, stage, pos_profile=None):
	"""Throw unless the drawer-cash row has an amount typed in (0 is allowed)."""
	for row in rows or []:
		if not _is_cash_mode(row.get("mode_of_payment"), pos_profile):
			continue
		value = row.get(amount_field)
		if value is None or str(value).strip() == "":
			frappe.throw(
				_("Enter the {0} cash amount for {1} before continuing.").format(
					stage, row.get("mode_of_payment")
				),
				title=_("Cash Amount Required"),
			)


@frappe.whitelist()
def get_opening_dialog_data():
	"""Get data required for opening shift dialog"""
	data = {}

	# Get POS Profiles where current user is defined in POS Profile User table
	pos_profiles_data = frappe.db.sql(
		"""
		SELECT DISTINCT p.name, p.company, p.currency, p.warehouse, p.selling_price_list
		FROM `tabPOS Profile` p
		INNER JOIN `tabPOS Profile User` u ON u.parent = p.name
		WHERE p.disabled = 0 AND u.user = %s
		ORDER BY p.name
		""",
		frappe.session.user,
		as_dict=1,
	)

	data["pos_profiles_data"] = pos_profiles_data

	# Derive companies from accessible POS Profiles
	company_names = []
	for profile in pos_profiles_data:
		if profile.company and profile.company not in company_names:
			company_names.append(profile.company)
	data["companies"] = [{"name": c} for c in company_names]

	# Get payment methods for POS profiles
	pos_profiles_list = [p.name for p in pos_profiles_data]

	if pos_profiles_list:
		data["payments_method"] = frappe.get_list(
			"POS Payment Method",
			filters={"parent": ["in", pos_profiles_list]},
			fields=["*"],
			limit_page_length=0,
			order_by="parent",
			ignore_permissions=True,
		)

		# Set currency from pos profile
		for mode in data["payments_method"]:
			mode["currency"] = frappe.get_cached_value("POS Profile", mode["parent"], "currency")
			mode["is_cash"] = _is_cash_mode(mode.get("mode_of_payment"), mode.get("parent"))
	else:
		data["payments_method"] = []

	return data


@frappe.whitelist()
def check_opening_shift(user=None):
	"""Check if user has an open shift"""
	if not user:
		user = frappe.session.user

	open_shifts = frappe.db.get_all(
		"POS Opening Shift",
		filters={
			"user": user,
			"pos_closing_shift": ["is", "not set"],
			"docstatus": 1,
			"status": "Open",
		},
		fields=["name", "pos_profile", "period_start_date"],
		order_by="period_start_date desc",
	)

	if not open_shifts:
		return None

	# Get the latest open shift
	shift_data = open_shifts[0]
	data = {}
	data["pos_opening_shift"] = frappe.get_doc("POS Opening Shift", shift_data["name"])
	data["pos_profile"] = frappe.get_doc("POS Profile", shift_data["pos_profile"])
	data["company"] = frappe.get_doc("Company", data["pos_profile"].company)

	return data


@frappe.whitelist()
def create_opening_shift(pos_profile, company, balance_details):
	"""Create a new POS Opening Shift"""
	balance_details = json.loads(balance_details) if isinstance(balance_details, str) else balance_details

	# Cashiers must declare the cash float they start with
	_require_cash_amounts(balance_details, "opening_amount", _("opening"), pos_profile)

	# Check if user already has an open shift
	existing_shift = check_opening_shift(frappe.session.user)
	if existing_shift:
		frappe.throw(_("You already have an open shift: {0}").format(existing_shift["pos_opening_shift"].name))

	new_pos_opening = frappe.get_doc(
		{
			"doctype": "POS Opening Shift",
			"period_start_date": get_datetime(),
			"posting_date": nowdate(),
			"posting_time": nowtime(),
			"user": frappe.session.user,
			"pos_profile": pos_profile,
			"company": company,
			"status": "Open",
		}
	)

	# Add balance details - map opening_amount to amount
	formatted_balance_details = []
	for detail in balance_details:
		formatted_balance_details.append({
			"mode_of_payment": detail.get("mode_of_payment"),
			"amount": detail.get("opening_amount", 0)
		})

	new_pos_opening.set("balance_details", formatted_balance_details)
	new_pos_opening.insert(ignore_permissions=True)
	new_pos_opening.submit()

	data = {}
	data["pos_opening_shift"] = new_pos_opening.as_dict()
	data["pos_profile"] = frappe.get_doc("POS Profile", pos_profile)
	data["company"] = frappe.get_doc("Company", company)

	return data


@frappe.whitelist()
def get_closing_shift_data(opening_shift):
	"""Get data for closing shift"""
	from pos_next.pos_next.doctype.pos_closing_shift.pos_closing_shift import make_closing_shift_from_opening

	try:
		# Get the opening shift document
		opening_shift_doc = frappe.get_doc("POS Opening Shift", opening_shift)

		# Convert to dict with proper datetime serialization
		opening_shift_dict = opening_shift_doc.as_dict()
		opening_shift_json = json.dumps(opening_shift_dict, default=str)

		# Create closing shift from opening shift
		closing_data = make_closing_shift_from_opening(opening_shift_json)

		# Convert the result to a serializable dict using frappe's as_dict which handles datetime
		if hasattr(closing_data, 'as_dict'):
			result = closing_data.as_dict()
			for payment in result.get("payment_reconciliation") or []:
				payment["is_cash"] = _is_cash_mode(payment.get("mode_of_payment"), result.get("pos_profile"))
			# Ensure all values are JSON serializable by converting to JSON and back
			return json.loads(json.dumps(result, default=str))
		return closing_data
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get Closing Shift Data Error")
		frappe.throw(_("Error getting closing shift data: {0}").format(str(e)))


@frappe.whitelist()
def submit_closing_shift(closing_shift):
	"""Submit closing shift"""
	from pos_next.pos_next.doctype.pos_closing_shift.pos_closing_shift import submit_closing_shift as submit_shift

	# closing_shift is already a JSON string from frontend
	# If it's a dict, convert to JSON string
	if isinstance(closing_shift, dict):
		closing_shift = json.dumps(closing_shift)

	# Cashiers must count and enter the cash in the drawer
	closing_values = json.loads(closing_shift)
	_require_cash_amounts(
		closing_values.get("payment_reconciliation") or [],
		"closing_amount",
		_("closing"),
		closing_values.get("pos_profile"),
	)

	try:
		result = submit_shift(closing_shift)
		return {"name": result, "status": "success"}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Submit Closing Shift Error")
		frappe.throw(_("Error submitting closing shift: {0}").format(str(e)))

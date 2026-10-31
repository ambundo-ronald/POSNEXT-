import json
from datetime import datetime, timedelta

import frappe
from frappe.utils import cint, get_time, getdate, now_datetime, nowdate, nowtime


GLOBAL_SETTINGS_DOCTYPE = "POS Next Global Settings"


def run_shift_automation():
	"""Open and close POS shifts based on POS Next Global Settings."""
	try:
		settings = frappe.get_single(GLOBAL_SETTINGS_DOCTYPE)
	except Exception:
		return

	current_date = nowdate()

	close_cutoff = _get_due_close_cutoff(settings)
	if close_cutoff:
		queued = close_open_shifts(close_cutoff)
		frappe.db.set_single_value(
			GLOBAL_SETTINGS_DOCTYPE,
			"last_auto_shift_close_date",
			close_cutoff.date(),
			update_modified=False,
		)
		frappe.logger("pos_next").info(
			f"Auto shift close: {queued} shift(s) opened before {close_cutoff} queued for closing"
		)

	if _is_due(settings, "enable_auto_shift_open", "auto_shift_open_time", "last_auto_shift_open_date"):
		opened_count = open_configured_shifts()
		frappe.db.set_single_value(
			GLOBAL_SETTINGS_DOCTYPE,
			"last_auto_shift_open_date",
			current_date,
			update_modified=False,
		)
		frappe.logger("pos_next").info(f"Auto shift open completed: {opened_count} shift(s) opened")


def _is_due(settings, enabled_field, time_field, last_run_field):
	if not cint(settings.get(enabled_field)):
		return False

	target_time = settings.get(time_field)
	if not target_time:
		return False

	if str(settings.get(last_run_field) or "") == nowdate():
		return False

	return get_time(nowtime()) >= get_time(target_time)


def _get_due_close_cutoff(settings):
	"""
	Return the most recent scheduled close time if it has not been handled yet.

	The scheduler runs every 5 minutes, so a close time such as 23:59:59 is
	never hit exactly. Once the time passes (or the day rolls over), the
	missed run is caught up on the next tick.
	"""
	if not cint(settings.get("enable_auto_shift_close")):
		return None

	target_time = settings.get("auto_shift_close_time")
	if not target_time:
		return None

	now = now_datetime()
	cutoff = datetime.combine(now.date(), get_time(target_time))
	if now < cutoff:
		cutoff -= timedelta(days=1)

	last_run = settings.get("last_auto_shift_close_date")
	if last_run and getdate(last_run) >= cutoff.date():
		return None

	return cutoff


def close_open_shifts(cutoff):
	"""Queue a closing job for each shift opened before the cutoff."""
	open_shifts = frappe.get_all(
		"POS Opening Shift",
		filters={
			"docstatus": 1,
			"status": "Open",
			"period_start_date": ["<", cutoff],
		},
		pluck="name",
		order_by="period_start_date asc",
	)

	# One job per shift so a large shift cannot time out or block the rest.
	for name in open_shifts:
		frappe.enqueue(
			"pos_next.tasks.shift_automation.close_shift",
			queue="long",
			timeout=3600,
			job_id=f"pos_next_auto_close::{name}",
			deduplicate=True,
			opening_shift=name,
		)

	return len(open_shifts)


def close_shift(opening_shift):
	from pos_next.pos_next.doctype.pos_closing_shift.pos_closing_shift import (
		make_closing_shift_from_opening,
	)

	try:
		opening_doc = frappe.get_doc("POS Opening Shift", opening_shift)
		if opening_doc.docstatus != 1 or opening_doc.status != "Open":
			return

		closing_doc = make_closing_shift_from_opening(
			json.dumps(opening_doc.as_dict(), default=str)
		)
		_set_sales_amounts_as_closing_amounts(closing_doc)
		closing_doc.flags.ignore_permissions = True
		closing_doc.save()
		closing_doc.submit()
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(
			title=f"Auto shift close failed for {opening_shift}",
			message=frappe.get_traceback(),
		)


def _set_sales_amounts_as_closing_amounts(closing_doc):
	"""Auto-close using sales collected during the shift, excluding opening float."""
	for payment in closing_doc.get("payment_reconciliation", []):
		sales_amount = (payment.expected_amount or 0) - (payment.opening_amount or 0)
		payment.opening_amount = 0
		payment.expected_amount = sales_amount
		payment.closing_amount = sales_amount


def open_configured_shifts():
	profiles = frappe.get_all(
		"POS Profile",
		filters={"disabled": 0},
		fields=["name", "company"],
		order_by="name asc",
	)

	opened_count = 0
	for profile in profiles:
		users = frappe.get_all(
			"POS Profile User",
			filters={"parent": profile.name},
			fields=["user"],
		)

		for row in users:
			user = row.get("user")
			if not user or not cint(frappe.db.get_value("User", user, "enabled")):
				continue

			if _has_open_shift(user):
				continue

			try:
				opening_doc = frappe.new_doc("POS Opening Shift")
				opening_doc.period_start_date = now_datetime()
				opening_doc.posting_date = getdate()
				opening_doc.user = user
				opening_doc.pos_profile = profile.name
				opening_doc.company = profile.company
				opening_doc.set("balance_details", _get_zero_opening_balances(profile.name))
				opening_doc.flags.ignore_permissions = True
				opening_doc.insert()
				opening_doc.submit()
				opened_count += 1
			except Exception:
				frappe.log_error(
					title=f"Auto shift open failed for {profile.name} / {user}",
					message=frappe.get_traceback(),
				)

	return opened_count


def _has_open_shift(user):
	return bool(
		frappe.db.exists(
			"POS Opening Shift",
			{
				"user": user,
				"docstatus": 1,
				"status": "Open",
			},
		)
	)


def _get_zero_opening_balances(pos_profile):
	payment_methods = frappe.get_all(
		"POS Payment Method",
		filters={"parent": pos_profile},
		fields=["mode_of_payment"],
		order_by="idx asc",
	)

	return [
		{"mode_of_payment": row.mode_of_payment, "amount": 0}
		for row in payment_methods
		if row.mode_of_payment
	]

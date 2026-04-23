# -*- coding: utf-8 -*-
# Copyright (c) 2026, BrainWise and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from pos_next.api.partial_payments import create_payment_entry
from pos_next.api.smsenabler_mpesa import (
	SMS_REGISTER_DOCTYPE,
	_get_phone_mop_for_company,
)


AMOUNT_TOLERANCE = 0.01


class SMSEnablerPaymentEntrySync(Document):
	def validate(self):
		self.sync_limit = max(cint(self.sync_limit or 0), 0)


def _find_existing_payment_entry(invoice_name, transaction_id=None, amount=None):
	conditions = [
		"pe.docstatus = 1",
		"pe.payment_type = 'Receive'",
		"per.reference_doctype = 'Sales Invoice'",
		"per.reference_name = %(invoice)s",
	]
	params = {"invoice": invoice_name}

	if transaction_id:
		conditions.append("pe.reference_no = %(transaction_id)s")
		params["transaction_id"] = transaction_id
	elif amount:
		conditions.append("ABS(pe.paid_amount - %(amount)s) < 0.01")
		params["amount"] = flt(amount)

	rows = frappe.db.sql(
		f"""
		SELECT pe.name
		FROM `tabPayment Entry` pe
		INNER JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
		WHERE {" AND ".join(conditions)}
		ORDER BY pe.creation DESC
		LIMIT 2
		""",
		params,
		as_dict=True,
	)

	if len(rows) == 1:
		return rows[0].name, None
	if len(rows) > 1:
		return None, _("Multiple matching Payment Entries already exist")
	return None, None


def _get_sync_candidates(company=None, sync_limit=0):
	conditions = [
		"COALESCE(reg.sales_invoice, '') != ''",
		"COALESCE(reg.payment_entry, '') = ''",
		"reg.status NOT IN ('Duplicate', 'Failed Parse')",
	]
	params = {}

	if company:
		conditions.append(
			"(reg.company = %(company)s OR (COALESCE(reg.company, '') = '' AND inv.company = %(company)s))"
		)
		params["company"] = company

	limit_sql = ""
	if sync_limit:
		limit_sql = "LIMIT %(sync_limit)s"
		params["sync_limit"] = cint(sync_limit)

	return frappe.db.sql(
		f"""
		SELECT
			reg.name,
			reg.sales_invoice,
			reg.amount,
			reg.transaction_id,
			reg.status,
			reg.company,
			reg.customer,
			reg.mode_of_payment,
			reg.received_at,
			inv.company AS invoice_company,
			inv.customer AS invoice_customer,
			inv.docstatus AS invoice_docstatus,
			inv.is_return AS invoice_is_return,
			inv.outstanding_amount,
			inv.posting_date
		FROM `tab{SMS_REGISTER_DOCTYPE}` reg
		LEFT JOIN `tabSales Invoice` inv ON inv.name = reg.sales_invoice
		WHERE {" AND ".join(conditions)}
		ORDER BY reg.received_at ASC, reg.creation ASC
		{limit_sql}
		""",
		params,
		as_dict=True,
	)


def _get_safe_posting_date(row):
	received_date = getdate(row.received_at) if row.received_at else getdate(nowdate())
	invoice_date = getdate(row.posting_date) if row.posting_date else received_date
	return str(max(received_date, invoice_date))


def _update_sms_payment(row, payment_entry=None, mode_of_payment=None):
	values = {
		"payment_entry": payment_entry,
		"status": "Consumed" if payment_entry else "Matched",
		"company": row.invoice_company or row.company,
		"customer": row.invoice_customer or row.customer,
	}
	if mode_of_payment:
		values["mode_of_payment"] = mode_of_payment

	frappe.db.set_value(SMS_REGISTER_DOCTYPE, row.name, values, update_modified=True)


def _build_summary_lines(result):
	lines = [
		"Candidates: {0}".format(result["candidate_count"]),
		"Created Payment Entries: {0}".format(result["created_payment_entries"]),
		"Linked Existing Payment Entries: {0}".format(result["linked_existing_count"]),
		"Skipped: {0}".format(result["skipped_count"]),
		"Failed: {0}".format(result["failed_count"]),
	]

	if result["details"]:
		lines.append("")
		lines.extend(result["details"])

	return "\n".join(lines)


def execute_sync(company=None, sync_limit=0):
	candidates = _get_sync_candidates(company=company, sync_limit=sync_limit)
	result = {
		"candidate_count": len(candidates),
		"created_payment_entries": 0,
		"linked_existing_count": 0,
		"skipped_count": 0,
		"failed_count": 0,
		"details": [],
	}

	for row in candidates:
		try:
			amount = flt(row.amount)
			if not row.sales_invoice:
				result["skipped_count"] += 1
				result["details"].append("{0}: skipped, no Sales Invoice link.".format(row.name))
				continue

			if not row.invoice_docstatus:
				result["skipped_count"] += 1
				result["details"].append(
					"{0}: skipped, Sales Invoice {1} no longer exists.".format(row.name, row.sales_invoice)
				)
				continue

			if cint(row.invoice_docstatus) != 1:
				result["skipped_count"] += 1
				result["details"].append(
					"{0}: skipped, Sales Invoice {1} is not submitted.".format(row.name, row.sales_invoice)
				)
				continue

			if cint(row.invoice_is_return):
				result["skipped_count"] += 1
				result["details"].append(
					"{0}: skipped, Sales Invoice {1} is a return.".format(row.name, row.sales_invoice)
				)
				continue

			if amount <= 0:
				result["skipped_count"] += 1
				result["details"].append("{0}: skipped, payment amount is zero.".format(row.name))
				continue

			existing_payment_entry, duplicate_reason = _find_existing_payment_entry(
				row.sales_invoice,
				transaction_id=row.transaction_id,
				amount=amount,
			)
			if existing_payment_entry:
				_update_sms_payment(row, payment_entry=existing_payment_entry, mode_of_payment=row.mode_of_payment)
				result["linked_existing_count"] += 1
				result["details"].append(
					"{0}: linked existing Payment Entry {1}.".format(row.name, existing_payment_entry)
				)
				continue

			if duplicate_reason:
				result["skipped_count"] += 1
				result["details"].append("{0}: skipped, {1}.".format(row.name, duplicate_reason))
				continue

			outstanding = flt(row.outstanding_amount)
			if outstanding <= AMOUNT_TOLERANCE:
				result["skipped_count"] += 1
				result["details"].append(
					"{0}: skipped, invoice {1} is already fully paid and has no matching Payment Entry.".format(
						row.name, row.sales_invoice
					)
				)
				continue

			if amount > outstanding + AMOUNT_TOLERANCE:
				result["skipped_count"] += 1
				result["details"].append(
					"{0}: skipped, amount {1} exceeds outstanding {2} on invoice {3}.".format(
						row.name,
						frappe.format_value(amount, {"fieldtype": "Currency"}),
						frappe.format_value(outstanding, {"fieldtype": "Currency"}),
						row.sales_invoice,
					)
				)
				continue

			mode_of_payment = row.mode_of_payment or _get_phone_mop_for_company(row.invoice_company)
			if not mode_of_payment:
				result["skipped_count"] += 1
				result["details"].append(
					"{0}: skipped, no valid Phone mode of payment is configured for company {1}.".format(
						row.name, row.invoice_company
					)
				)
				continue

			payment_entry = create_payment_entry(
				invoice_name=row.sales_invoice,
				amount=amount,
				mode_of_payment=mode_of_payment,
				reference_no=row.transaction_id or row.name,
				remarks="SMS Enabler sync backfill for {0}".format(row.name),
				posting_date=_get_safe_posting_date(row),
			)
			_update_sms_payment(row, payment_entry=payment_entry, mode_of_payment=mode_of_payment)
			result["created_payment_entries"] += 1
			result["details"].append(
				"{0}: created Payment Entry {1} for invoice {2}.".format(
					row.name, payment_entry, row.sales_invoice
				)
			)
		except Exception as exc:
			result["failed_count"] += 1
			result["details"].append("{0}: failed, {1}".format(row.name, str(exc)))
			frappe.log_error(
				title="SMS Enabler Payment Entry Sync Failed",
				message=frappe.get_traceback(),
			)

	return result


@frappe.whitelist()
def run_sync(docname):
	doc = frappe.get_doc("SMS Enabler Payment Entry Sync", docname)
	if not doc.has_permission("write"):
		frappe.throw(_("You do not have permission to run this sync"), frappe.PermissionError)
	if doc.status == "Running":
		frappe.throw(_("This sync is already running"))

	doc.status = "Running"
	doc.last_run_at = now_datetime()
	doc.created_payment_entries = 0
	doc.linked_existing_count = 0
	doc.skipped_count = 0
	doc.failed_count = 0
	doc.run_summary = ""
	doc.last_error = ""
	doc.flags.ignore_permissions = True
	doc.save()
	frappe.db.commit()

	try:
		result = execute_sync(company=doc.company, sync_limit=doc.sync_limit)
		doc.status = "Completed"
		doc.created_payment_entries = result["created_payment_entries"]
		doc.linked_existing_count = result["linked_existing_count"]
		doc.skipped_count = result["skipped_count"]
		doc.failed_count = result["failed_count"]
		doc.run_summary = _build_summary_lines(result)
		doc.last_error = ""
		doc.flags.ignore_permissions = True
		doc.save()
		frappe.db.commit()
		return result
	except Exception:
		doc.status = "Failed"
		doc.last_error = frappe.get_traceback()
		doc.flags.ignore_permissions = True
		doc.save()
		frappe.db.commit()
		raise

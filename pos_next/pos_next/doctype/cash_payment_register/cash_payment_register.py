# -*- coding: utf-8 -*-
# Copyright (c) 2026, BrainWise and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate


AMOUNT_TOLERANCE = 0.01


class CashPaymentRegister(Document):
	def validate(self):
		if not self.status:
			self.status = "Pending"
		if not self.posting_date:
			self.posting_date = nowdate()
		self.amount = flt(self.amount)


def find_matching_payment_entry(invoice_name, mode_of_payment, amount, reference_no=None):
	conditions = [
		"pe.docstatus = 1",
		"pe.payment_type = 'Receive'",
		"pe.mode_of_payment = %(mode_of_payment)s",
		"per.reference_doctype = 'Sales Invoice'",
		"per.reference_name = %(invoice_name)s",
	]
	params = {
		"invoice_name": invoice_name,
		"mode_of_payment": mode_of_payment,
	}

	if reference_no:
		conditions.append("pe.reference_no = %(reference_no)s")
		params["reference_no"] = reference_no
	else:
		conditions.append("ABS(pe.paid_amount - %(amount)s) < 0.01")
		params["amount"] = flt(amount)

	rows = frappe.db.sql(
		f"""
		SELECT pe.name
		FROM `tabPayment Entry` pe
		INNER JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
		WHERE {" AND ".join(conditions)}
		ORDER BY pe.creation DESC
		LIMIT 1
		""",
		params,
		as_dict=True,
	)
	return rows[0].name if rows else None


def create_or_get_cash_payment_register(invoice_doc, amount, mode_of_payment, reference_no=None, remarks=None):
	filters = {
		"sales_invoice": invoice_doc.name,
		"mode_of_payment": mode_of_payment,
		"amount": flt(amount),
	}
	if reference_no:
		filters["reference_no"] = reference_no

	existing = frappe.db.get_value("Cash Payment Register", filters, "name")
	if existing:
		return existing

	doc = frappe.new_doc("Cash Payment Register")
	doc.status = "Pending"
	doc.posting_date = invoice_doc.posting_date or nowdate()
	doc.company = invoice_doc.company
	doc.cashier = frappe.session.user
	doc.sales_invoice = invoice_doc.name
	doc.customer = invoice_doc.customer
	doc.pos_profile = invoice_doc.pos_profile
	doc.mode_of_payment = mode_of_payment
	doc.amount = flt(amount)
	doc.reference_no = reference_no
	doc.remarks = remarks
	doc.flags.ignore_permissions = True
	doc.insert()
	frappe.db.commit()
	return doc.name


def mark_cash_payment_register_reconciled(name, payment_entry):
	frappe.db.set_value(
		"Cash Payment Register",
		name,
		{
			"status": "Reconciled",
			"payment_entry": payment_entry,
			"last_error": "",
		},
		update_modified=True,
	)
	frappe.db.commit()


def mark_cash_payment_register_failed(name, error_message):
	frappe.db.set_value(
		"Cash Payment Register",
		name,
		{
			"status": "Failed",
			"last_error": str(error_message or "")[:500],
		},
		update_modified=True,
	)
	frappe.db.commit()


def register_inline_pos_cash_payments(invoice_doc):
	"""Record cash rows paid directly on a submitted POS Sales Invoice."""
	if not invoice_doc or not invoice_doc.get("is_pos"):
		return []

	from pos_next.payment_reconciliation import get_mode_of_payment_type

	registered = []
	for idx, payment in enumerate(invoice_doc.get("payments") or [], 1):
		mode_of_payment = payment.get("mode_of_payment")
		amount = flt(payment.get("amount"))
		if amount <= AMOUNT_TOLERANCE:
			continue

		if get_mode_of_payment_type(mode_of_payment) != "cash":
			continue

		register_name = create_or_get_cash_payment_register(
			invoice_doc=invoice_doc,
			amount=amount,
			mode_of_payment=mode_of_payment,
			reference_no=f"INLINE-{invoice_doc.name}-{idx}",
			remarks=f"Inline POS cash payment - {mode_of_payment}",
		)
		mark_cash_payment_register_reconciled(register_name, None)
		registered.append(register_name)

	return registered


@frappe.whitelist()
def retry_cash_payment_entry(name):
	doc = frappe.get_doc("Cash Payment Register", name)
	if not doc.has_permission("write"):
		frappe.throw(_("You do not have permission to retry this cash payment"), frappe.PermissionError)

	existing_payment_entry = doc.payment_entry or find_matching_payment_entry(
		doc.sales_invoice,
		doc.mode_of_payment,
		doc.amount,
		doc.reference_no,
	)
	if existing_payment_entry:
		mark_cash_payment_register_reconciled(doc.name, existing_payment_entry)
		return {"success": True, "payment_entry": existing_payment_entry}

	try:
		from pos_next.api.partial_payments import create_payment_entry

		payment_entry = create_payment_entry(
			invoice_name=doc.sales_invoice,
			amount=doc.amount,
			mode_of_payment=doc.mode_of_payment,
			reference_no=doc.reference_no or doc.name,
			remarks=doc.remarks or "Cash payment register retry",
			posting_date=str(doc.posting_date) if doc.posting_date else None,
		)
		mark_cash_payment_register_reconciled(doc.name, payment_entry)
		return {"success": True, "payment_entry": payment_entry}
	except Exception as exc:
		mark_cash_payment_register_failed(doc.name, exc)
		raise

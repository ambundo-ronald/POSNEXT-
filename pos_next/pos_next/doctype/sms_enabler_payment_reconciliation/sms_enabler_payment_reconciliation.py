# Copyright (c) 2026, BrainWise and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime

SMS_REGISTER_DOCTYPE = "SMS Enabler Payment Register"
AMOUNT_TOLERANCE = 0.01


class SMSEnablerPaymentReconciliation(Document):
	def save(self, *args, **kwargs):
		return

	def db_insert(self, *args, **kwargs):
		pass

	def load_from_db(self, *args, **kwargs):
		pass

	def db_update(self, *args, **kwargs):
		pass

	def delete(self, *args, **kwargs):
		pass

	@staticmethod
	def get_list(args):
		pass

	@staticmethod
	def get_count(args):
		pass

	@staticmethod
	def get_stats(args):
		pass


def _parse_names(value):
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except ValueError:
			value = [item.strip() for item in value.split(",") if item.strip()]

	names = []
	for item in value or []:
		if isinstance(item, dict):
			name = item.get("name") or item.get("sales_invoice") or item.get("sms_payment")
		else:
			name = item
		if name:
			names.append(str(name).strip())
	return names


@frappe.whitelist()
def get_outstanding_invoices(
	company=None, pos_profile=None, customer=None, from_date=None, to_date=None, invoice_name=None
):
	filters = {
		"docstatus": 1,
		"is_return": 0,
		"outstanding_amount": [">", 0],
	}
	if company:
		filters["company"] = company
	if pos_profile:
		filters["pos_profile"] = pos_profile
	if customer:
		filters["customer"] = customer
	if invoice_name:
		filters["name"] = invoice_name
	if from_date and to_date:
		filters["posting_date"] = ["between", [from_date, to_date]]
	elif from_date:
		filters["posting_date"] = [">=", from_date]
	elif to_date:
		filters["posting_date"] = ["<=", to_date]

	return frappe.get_all(
		"Sales Invoice",
		filters=filters,
		fields=[
			"name as sales_invoice",
			"posting_date",
			"customer",
			"customer_name",
			"company",
			"grand_total",
			"outstanding_amount",
			"currency",
		],
		order_by="posting_date asc, name asc",
		limit_page_length=200,
	)


@frappe.whitelist()
def get_unreconciled_sms_payments(
	company=None, pos_profile=None, search=None, from_date=None, to_date=None
):
	from pos_next.pos_next.doctype.pos_settings.pos_settings import get_global_sms_enabler_settings

	profile_mode = not get_global_sms_enabler_settings().get("sms_enabler_enabled")
	if profile_mode and not pos_profile:
		return []

	filters = {
		"status": ["in", ["Pending", "Matched", "Partially Allocated"]],
	}
	if company:
		filters["company"] = ["in", [company, "", None]]
	if profile_mode:
		filters["pos_profile"] = pos_profile
	if from_date and to_date:
		filters["received_at"] = [
			"between",
			[
				get_datetime(f"{from_date} 00:00:00"),
				get_datetime(f"{to_date} 23:59:59"),
			],
		]
	elif from_date:
		filters["received_at"] = [">=", get_datetime(f"{from_date} 00:00:00")]
	elif to_date:
		filters["received_at"] = ["<=", get_datetime(f"{to_date} 23:59:59")]

	payments = frappe.get_all(
		SMS_REGISTER_DOCTYPE,
		filters=filters,
		fields=[
			"name as sms_payment",
			"received_at",
			"source",
			"sender",
			"transaction_id",
			"amount",
			"allocated_amount",
			"available_amount",
			"payer_name",
			"payer_phone",
			"account_reference",
			"company",
			"pos_profile",
			"mode_of_payment",
			"raw_message",
		],
		order_by="received_at desc",
		limit_page_length=200,
	)

	available_payments = []
	for payment in payments:
		original_amount = flt(payment.get("amount"))
		allocated_amount = max(flt(payment.get("allocated_amount")), 0)
		available_amount = max(original_amount - allocated_amount, 0)
		if available_amount <= AMOUNT_TOLERANCE:
			continue
		payment["original_amount"] = original_amount
		payment["allocated_amount"] = allocated_amount
		payment["available_amount"] = available_amount
		payment["amount"] = available_amount
		payment["allocation_status"] = (
			_("Partially Allocated") if allocated_amount > 0 else _("Unallocated")
		)
		available_payments.append(payment)
	payments = available_payments

	search = (search or "").strip().lower()
	if not search:
		return payments

	filtered = []
	for payment in payments:
		values = [
			payment.get("source"),
			payment.get("sender"),
			payment.get("transaction_id"),
			payment.get("payer_name"),
			payment.get("payer_phone"),
			payment.get("account_reference"),
			payment.get("raw_message"),
		]
		if any(search in str(value or "").lower() for value in values):
			filtered.append(payment)
	return filtered


@frappe.whitelist()
def process_sms_enabler_reconciliation(invoice_names, sms_payment_names):
	from pos_next.api.smsenabler_mpesa import (
		_apply_sms_payment_to_invoice,
		_get_sms_payment_amounts,
	)

	invoice_names = _parse_names(invoice_names)
	sms_payment_names = _parse_names(sms_payment_names)

	if not invoice_names:
		frappe.throw(_("Please select at least one invoice."))
	if not sms_payment_names:
		frappe.throw(_("Please select at least one SMS payment."))

	invoices = [frappe.get_doc("Sales Invoice", name) for name in invoice_names]
	first_invoice = invoices[0]
	customer = first_invoice.customer
	company = first_invoice.company
	currency = first_invoice.currency
	debit_to = first_invoice.debit_to

	for invoice in invoices:
		if invoice.docstatus != 1:
			frappe.throw(_("Invoice {0} is not submitted.").format(invoice.name))
		if invoice.customer != customer:
			frappe.throw(_("All selected invoices must belong to the same customer."))
		if invoice.company != company:
			frappe.throw(_("All selected invoices must belong to the same company."))
		if invoice.pos_profile != first_invoice.pos_profile:
			frappe.throw(_("All selected invoices must belong to the same POS Profile."))
		if invoice.currency != currency:
			frappe.throw(_("All selected invoices must use the same currency."))
		if invoice.debit_to != debit_to:
			frappe.throw(_("All selected invoices must use the same receivable account."))
		if flt(invoice.outstanding_amount) <= AMOUNT_TOLERANCE:
			frappe.throw(_("Invoice {0} has no outstanding amount.").format(invoice.name))

	remaining_by_invoice = {invoice.name: flt(invoice.outstanding_amount) for invoice in invoices}
	sms_payments = [frappe.get_doc(SMS_REGISTER_DOCTYPE, name) for name in sms_payment_names]

	payment_entries = []
	processed = []

	for sms_payment in sms_payments:
		if sms_payment.status not in ("Pending", "Matched", "Partially Allocated"):
			frappe.throw(_("SMS payment {0} is already {1}.").format(sms_payment.name, sms_payment.status))
		if sms_payment.pos_profile and sms_payment.pos_profile != first_invoice.pos_profile:
			frappe.throw(
				_("SMS payment {0} belongs to POS Profile {1}.").format(
					sms_payment.name, sms_payment.pos_profile
				)
			)

		_total_amount, _allocated_amount, amount_to_allocate = _get_sms_payment_amounts(sms_payment)
		if amount_to_allocate <= AMOUNT_TOLERANCE:
			continue

		for invoice in invoices:
			if amount_to_allocate <= AMOUNT_TOLERANCE:
				break

			available = remaining_by_invoice.get(invoice.name, 0)
			if available <= AMOUNT_TOLERANCE:
				continue

			allocated = min(available, amount_to_allocate)
			invoice.reload()
			result = _apply_sms_payment_to_invoice(
				sms_payment,
				invoice,
				requested_amount=allocated,
			)
			sms_payment.reload()
			if result["payment_entry"] not in payment_entries:
				payment_entries.append(result["payment_entry"])
			processed.append(result)
			remaining_by_invoice[invoice.name] = flt(
				available - result["allocated_now"]
			)
			amount_to_allocate = flt(
				amount_to_allocate - result["allocated_now"]
			)

	frappe.db.commit()
	return {
		"success": True,
		"payment_entries": payment_entries,
		"processed": processed,
	}

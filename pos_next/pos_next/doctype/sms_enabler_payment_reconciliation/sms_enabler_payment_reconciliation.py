# Copyright (c) 2026, BrainWise and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate

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
def get_outstanding_invoices(company=None, customer=None, from_date=None, to_date=None, invoice_name=None):
	filters = {
		"docstatus": 1,
		"is_return": 0,
		"outstanding_amount": [">", 0],
	}
	if company:
		filters["company"] = company
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
def get_unreconciled_sms_payments(company=None, search=None, from_date=None, to_date=None):
	filters = {
		"status": "Pending",
		"sales_invoice": ["in", ["", None]],
		"payment_entry": ["in", ["", None]],
	}
	if company:
		filters["company"] = ["in", [company, "", None]]
	if from_date and to_date:
		filters["received_at"] = ["between", [from_date, to_date]]
	elif from_date:
		filters["received_at"] = [">=", from_date]
	elif to_date:
		filters["received_at"] = ["<=", to_date]

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
			"payer_name",
			"payer_phone",
			"account_reference",
			"company",
			"mode_of_payment",
			"raw_message",
		],
		order_by="received_at desc",
		limit_page_length=200,
	)

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


def _create_sms_payment_entry(invoice_allocations, sms_payment, customer, company, mode_of_payment):
	from pos_next.api.partial_payments import _resolve_payment_account

	amount = flt(sms_payment.amount)
	first_invoice = frappe.get_doc("Sales Invoice", invoice_allocations[0]["invoice"])
	sms_posting_date = getdate(sms_payment.received_at) if sms_payment.received_at else getdate(nowdate())
	latest_invoice_date = max(
		getdate(frappe.db.get_value("Sales Invoice", allocation["invoice"], "posting_date"))
		for allocation in invoice_allocations
	)
	posting_date = max(sms_posting_date, latest_invoice_date)

	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = "Receive"
	pe.posting_date = posting_date
	pe.party_type = "Customer"
	pe.party = customer
	pe.company = company
	pe.mode_of_payment = mode_of_payment
	pe.paid_from = first_invoice.debit_to
	pe.paid_to = _resolve_payment_account(
		mode_of_payment=mode_of_payment,
		company=company,
		invoice=first_invoice,
	)
	pe.paid_amount = amount
	pe.received_amount = amount
	pe.paid_from_account_currency = first_invoice.currency
	pe.paid_to_account_currency = first_invoice.currency
	pe.reference_no = (sms_payment.transaction_id or sms_payment.name)[:140]
	pe.reference_date = posting_date
	pe.remarks = _("SMS Enabler reconciliation for {0}").format(sms_payment.name)

	for allocation in invoice_allocations:
		invoice = frappe.get_doc("Sales Invoice", allocation["invoice"])
		pe.append(
			"references",
			{
				"reference_doctype": "Sales Invoice",
				"reference_name": invoice.name,
				"total_amount": invoice.grand_total,
				"outstanding_amount": invoice.outstanding_amount,
				"allocated_amount": allocation["amount"],
			},
		)

	pe.flags.ignore_permissions = True
	pe.insert()
	pe.submit()
	return pe.name


@frappe.whitelist()
def process_sms_enabler_reconciliation(invoice_names, sms_payment_names):
	from pos_next.api.smsenabler_mpesa import _get_phone_mop_for_company

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
		if invoice.currency != currency:
			frappe.throw(_("All selected invoices must use the same currency."))
		if invoice.debit_to != debit_to:
			frappe.throw(_("All selected invoices must use the same receivable account."))
		if flt(invoice.outstanding_amount) <= AMOUNT_TOLERANCE:
			frappe.throw(_("Invoice {0} has no outstanding amount.").format(invoice.name))

	remaining_by_invoice = {invoice.name: flt(invoice.outstanding_amount) for invoice in invoices}
	total_outstanding = sum(remaining_by_invoice.values())
	sms_payments = [frappe.get_doc(SMS_REGISTER_DOCTYPE, name) for name in sms_payment_names]
	total_sms = sum(flt(payment.amount) for payment in sms_payments)

	if total_sms > total_outstanding + AMOUNT_TOLERANCE:
		frappe.throw(
			_("Selected SMS amount {0} exceeds selected invoice outstanding amount {1}.").format(
				frappe.format_value(total_sms, {"fieldtype": "Currency"}),
				frappe.format_value(total_outstanding, {"fieldtype": "Currency"}),
			)
		)

	payment_entries = []
	processed = []

	for sms_payment in sms_payments:
		if sms_payment.status not in ("Pending", "Matched"):
			frappe.throw(_("SMS payment {0} is already {1}.").format(sms_payment.name, sms_payment.status))
		if sms_payment.payment_entry:
			frappe.throw(_("SMS payment {0} is already linked to Payment Entry {1}.").format(sms_payment.name, sms_payment.payment_entry))
		if sms_payment.sales_invoice:
			frappe.throw(_("SMS payment {0} is already linked to Sales Invoice {1}.").format(sms_payment.name, sms_payment.sales_invoice))

		amount_to_allocate = flt(sms_payment.amount)
		if amount_to_allocate <= 0:
			frappe.throw(_("SMS payment {0} has no valid amount.").format(sms_payment.name))

		allocations = []
		for invoice in invoices:
			if amount_to_allocate <= AMOUNT_TOLERANCE:
				break

			available = remaining_by_invoice.get(invoice.name, 0)
			if available <= AMOUNT_TOLERANCE:
				continue

			allocated = min(available, amount_to_allocate)
			allocations.append({"invoice": invoice.name, "amount": allocated})
			remaining_by_invoice[invoice.name] = flt(available - allocated)
			amount_to_allocate = flt(amount_to_allocate - allocated)

		if amount_to_allocate > AMOUNT_TOLERANCE:
			frappe.throw(_("Could not allocate full amount for SMS payment {0}.").format(sms_payment.name))

		mode_of_payment = sms_payment.mode_of_payment or _get_phone_mop_for_company(company)
		if not mode_of_payment:
			frappe.throw(_("No enabled Phone mode of payment is configured for company {0}.").format(company))

		payment_entry = _create_sms_payment_entry(
			invoice_allocations=allocations,
			sms_payment=sms_payment,
			customer=customer,
			company=company,
			mode_of_payment=mode_of_payment,
		)
		payment_entries.append(payment_entry)

		sms_payment.customer = customer
		sms_payment.company = company
		sms_payment.sales_invoice = allocations[0]["invoice"]
		sms_payment.mode_of_payment = mode_of_payment
		sms_payment.payment_entry = payment_entry
		sms_payment.status = "Consumed"
		sms_payment.flags.ignore_permissions = True
		sms_payment.save()

		processed.append(
			{
				"sms_payment": sms_payment.name,
				"payment_entry": payment_entry,
				"amount": flt(sms_payment.amount),
			}
		)

	frappe.db.commit()
	return {
		"success": True,
		"payment_entries": payment_entries,
		"processed": processed,
	}

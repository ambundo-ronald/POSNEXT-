# -*- coding: utf-8 -*-
"""Optional M-Pesa quick pay integration for POS Next.

This module ports the useful server-side behavior from the POS_Mpesa app while
keeping the dependency optional. If Navari's M-Pesa app is not installed, the
availability endpoint simply reports that M-Pesa is unavailable.
"""

from __future__ import unicode_literals

import json

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.utils import flt, nowdate


MPESA_SETTINGS_DOCTYPE = "Mpesa Settings"
MPESA_REGISTER_DOCTYPE = "Mpesa C2B Payment Register"
MPESA_SALES_INVOICE_FIELD = "sales_invoice"


def _doctype_exists(doctype):
	return bool(frappe.db.exists("DocType", doctype))


def _has_field(doctype, fieldname):
	if not _doctype_exists(doctype):
		return False

	return bool(frappe.get_meta(doctype).has_field(fieldname))


def _resolve_company(company=None, pos_profile=None, invoice=None):
	if company:
		return company

	if invoice:
		return frappe.db.get_value("Sales Invoice", invoice, "company")

	if pos_profile:
		return frappe.db.get_value("POS Profile", pos_profile, "company")

	return None


def _get_phone_mop_for_company(company):
	"""Get an enabled Phone-type Mode of Payment with an account for company."""
	if not company:
		return None

	phone_mops = frappe.get_all(
		"Mode of Payment",
		filters={"type": "Phone", "enabled": 1},
		fields=["name"],
	)

	for mop in phone_mops:
		account = frappe.db.get_value(
			"Mode of Payment Account",
			{"parent": mop.name, "company": company},
			"default_account",
		)
		if account:
			return mop.name

	return None


def _get_mpesa_shortcode_for_company(company):
	"""Get business shortcode from Mpesa Settings for the company."""
	if not company or not _doctype_exists(MPESA_SETTINGS_DOCTYPE):
		return None

	settings = frappe.get_all(
		MPESA_SETTINGS_DOCTYPE,
		filters={"company": company},
		fields=["name", "business_shortcode"],
		limit=1,
	)

	if settings and settings[0].get("business_shortcode"):
		return str(settings[0].business_shortcode)

	return None


def _ensure_sales_invoice_link_field():
	"""Create the optional Sales Invoice link field when the M-Pesa app exists."""
	if not _doctype_exists(MPESA_REGISTER_DOCTYPE):
		return False

	if _has_field(MPESA_REGISTER_DOCTYPE, MPESA_SALES_INVOICE_FIELD):
		return True

	create_custom_field(
		MPESA_REGISTER_DOCTYPE,
		{
			"fieldname": MPESA_SALES_INVOICE_FIELD,
			"label": "Sales Invoice",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"insert_after": "mode_of_payment",
			"read_only": 1,
			"allow_on_submit": 1,
			"no_copy": 1,
		},
	)
	frappe.clear_cache(doctype=MPESA_REGISTER_DOCTYPE)
	return True


def _normalize_phone(value):
	return "".join(ch for ch in str(value or "") if ch.isdigit())


def _get_customer_match_data(customer):
	if not customer:
		return {"phone": "", "name": ""}

	phone = get_customer_phone(customer)
	customer_name = frappe.db.get_value("Customer", customer, "customer_name") or customer

	return {
		"phone": _normalize_phone(phone),
		"name": str(customer_name or "").lower(),
	}


def _score_payment_match(payment, amount=0, customer_data=None):
	"""Score an incoming payment against the active invoice/customer context."""
	score = 0
	reasons = []
	amount = flt(amount or 0)
	customer_data = customer_data or {}

	payment_amount = flt(payment.get("transamount") or 0)
	if amount > 0:
		difference = abs(payment_amount - amount)
		if difference < 0.01:
			score += 70
			reasons.append(_("Exact amount"))
		elif difference <= max(1, amount * 0.02):
			score += 35
			reasons.append(_("Close amount"))

	customer_phone = customer_data.get("phone")
	payment_phone = _normalize_phone(payment.get("msisdn"))
	if customer_phone and payment_phone:
		if payment_phone.endswith(customer_phone[-9:]) or customer_phone.endswith(payment_phone[-9:]):
			score += 25
			reasons.append(_("Same phone"))

	customer_name = customer_data.get("name")
	payment_name = str(payment.get("full_name") or "").lower()
	if customer_name and payment_name:
		customer_tokens = {token for token in customer_name.split() if len(token) >= 3}
		payment_tokens = {token for token in payment_name.split() if len(token) >= 3}
		if customer_tokens and customer_tokens.intersection(payment_tokens):
			score += 10
			reasons.append(_("Name match"))

	if str(payment.get("posting_date") or "") == nowdate():
		score += 10
		reasons.append(_("Today"))

	if score >= 90:
		level = "High"
	elif score >= 60:
		level = "Suggested"
	else:
		level = "Low"

	payment["match_score"] = score
	payment["match_level"] = level
	payment["match_reasons"] = reasons
	payment["is_exact_amount"] = amount > 0 and abs(payment_amount - amount) < 0.01
	return payment


def _reference_matches_payment(payment, references):
	references = [str(ref or "").lower() for ref in references if ref]
	if not references:
		return False

	values = [
		payment.get("billrefnumber"),
		payment.get("transid"),
		payment.get("name"),
	]
	for value in values:
		value = str(value or "").lower()
		if value and any(ref in value or value in ref for ref in references):
			return True

	return False


def _phone_matches_payment(payment, phone_number):
	expected = _normalize_phone(phone_number)
	actual = _normalize_phone(payment.get("msisdn"))
	if not expected or not actual:
		return False

	return actual.endswith(expected[-9:]) or expected.endswith(actual[-9:])


def _build_mpesa_payment_fields():
	fields = [
		"name",
		"docstatus",
		"full_name",
		"transamount",
		"transid",
		"msisdn",
		"posting_date",
		"billrefnumber",
		"creation",
	]

	for fieldname in (MPESA_SALES_INVOICE_FIELD, "pos_invoice"):
		if _has_field(MPESA_REGISTER_DOCTYPE, fieldname) and fieldname not in fields:
			fields.append(fieldname)

	return fields


def _parse_mpesa_names(mpesa_payments):
	if isinstance(mpesa_payments, str):
		try:
			parsed = json.loads(mpesa_payments)
		except ValueError:
			parsed = [p.strip() for p in mpesa_payments.split(",") if p.strip()]
	else:
		parsed = mpesa_payments

	names = []
	for payment in parsed or []:
		if isinstance(payment, dict):
			name = payment.get("name") or payment.get("mpesa_payment_name")
		else:
			name = payment

		if name:
			names.append(str(name).strip())

	return names


@frappe.whitelist()
def check_mpesa_available(company=None, pos_profile=None):
	"""Return whether M-Pesa quick pay can be used for this company/profile."""
	company = _resolve_company(company=company, pos_profile=pos_profile)

	if not _doctype_exists(MPESA_SETTINGS_DOCTYPE) or not _doctype_exists(MPESA_REGISTER_DOCTYPE):
		return {
			"available": False,
			"reason": _("M-Pesa payment app is not installed"),
		}

	phone_mop = _get_phone_mop_for_company(company)
	shortcode = _get_mpesa_shortcode_for_company(company)

	return {
		"available": bool(phone_mop and shortcode),
		"mode_of_payment": phone_mop,
		"shortcode": shortcode,
		"company": company,
	}


@frappe.whitelist()
def get_mpesa_payments(company=None, pos_profile=None, search=None, amount=None, customer=None):
	"""Get pending draft M-Pesa C2B payments for the company.

	Like the source POS_Mpesa app, payment rows are returned only after a
	3-character search, but the pending count is always returned.
	"""
	company = _resolve_company(company=company, pos_profile=pos_profile)
	search = (search or "").strip()
	amount = flt(amount or 0)

	if not company or not _doctype_exists(MPESA_REGISTER_DOCTYPE):
		return {"count": 0, "payments": []}

	shortcode = _get_mpesa_shortcode_for_company(company)
	if not shortcode:
		return {"count": 0, "payments": []}

	base_filters = {
		"docstatus": 0,
		"businessshortcode": shortcode,
	}

	total_count = frappe.db.count(MPESA_REGISTER_DOCTYPE, base_filters)

	if len(search) < 3 and amount <= 0:
		return {"count": total_count, "payments": []}

	search_lower = search.lower()
	all_payments = frappe.get_all(
		MPESA_REGISTER_DOCTYPE,
		filters=base_filters,
		fields=[
			"name",
			"full_name",
			"transamount",
			"transid",
			"msisdn",
			"posting_date",
			"billrefnumber",
			"creation",
		],
		order_by="creation desc",
		limit_page_length=100,
	)

	customer_data = _get_customer_match_data(customer)
	payments = []
	for payment in all_payments:
		values = [
			payment.get("full_name"),
			payment.get("transid"),
			payment.get("billrefnumber"),
			payment.get("msisdn"),
			payment.get("name"),
		]
		search_match = len(search) >= 3 and any(search_lower in str(value or "").lower() for value in values)
		scored_payment = _score_payment_match(payment, amount=amount, customer_data=customer_data)

		if search_match or (amount > 0 and scored_payment.get("match_score", 0) > 0):
			payments.append(scored_payment)

	payments.sort(
		key=lambda item: (
			item.get("match_score", 0),
			item.get("is_exact_amount", False),
			str(item.get("creation") or ""),
		),
		reverse=True,
	)

	return {"count": total_count, "payments": payments}


@frappe.whitelist()
def get_customer_phone(customer=None):
	"""Return the best available phone number for a customer."""
	phone = ""

	if customer:
		contact = frappe.db.get_value(
			"Dynamic Link",
			{
				"link_doctype": "Customer",
				"link_name": customer,
				"parenttype": "Contact",
			},
			"parent",
		)

		if contact:
			phone = frappe.db.get_value("Contact", contact, "mobile_no") or ""
			if not phone:
				phone = frappe.db.get_value("Contact", contact, "phone") or ""

		if not phone:
			phone = frappe.db.get_value("Customer", customer, "mobile_no") or ""

	return phone


@frappe.whitelist()
def process_sales_invoice_payments(invoice=None, customer=None, company=None, mpesa_payments=None):
	"""Submit selected M-Pesa C2B entries and link them to a Sales Invoice."""
	if not invoice:
		frappe.throw(_("Sales Invoice is required"))

	if not frappe.db.exists("Sales Invoice", invoice):
		frappe.throw(_("Sales Invoice {0} does not exist").format(invoice))

	if not _doctype_exists(MPESA_REGISTER_DOCTYPE):
		frappe.throw(_("M-Pesa payment app is not installed"))

	invoice_doc = frappe.get_doc("Sales Invoice", invoice)
	company = _resolve_company(company=company, invoice=invoice) or invoice_doc.company
	customer = customer or invoice_doc.customer

	mpesa_names = _parse_mpesa_names(mpesa_payments)
	if not mpesa_names:
		frappe.throw(_("No M-Pesa payments selected"))

	phone_mop = _get_phone_mop_for_company(company)
	if not phone_mop:
		frappe.throw(_("No Phone type Mode of Payment configured for {0}").format(company))

	shortcode = _get_mpesa_shortcode_for_company(company)
	if not shortcode:
		frappe.throw(_("No Mpesa Settings found for {0}").format(company))

	_ensure_sales_invoice_link_field()

	processed = []
	for mpesa_name in mpesa_names:
		mpesa = frappe.get_doc(MPESA_REGISTER_DOCTYPE, mpesa_name)

		if str(mpesa.get("businessshortcode") or "") != shortcode:
			frappe.throw(_("M-Pesa payment {0} does not belong to company {1}").format(mpesa_name, company))

		if flt(mpesa.get("transamount") or 0) <= 0:
			frappe.throw(_("M-Pesa payment {0} has no valid amount").format(mpesa_name))

		if mpesa.docstatus == 2:
			frappe.throw(_("M-Pesa payment {0} is cancelled").format(mpesa_name))

		linked_invoice = mpesa.get(MPESA_SALES_INVOICE_FIELD) if _has_field(MPESA_REGISTER_DOCTYPE, MPESA_SALES_INVOICE_FIELD) else None
		if mpesa.docstatus == 1 and linked_invoice and linked_invoice != invoice:
			frappe.throw(_("M-Pesa payment {0} is already linked to {1}").format(mpesa_name, linked_invoice))

		if mpesa.docstatus == 0:
			if _has_field(MPESA_REGISTER_DOCTYPE, "customer"):
				mpesa.customer = customer
			if _has_field(MPESA_REGISTER_DOCTYPE, "mode_of_payment"):
				mpesa.mode_of_payment = phone_mop
			if _has_field(MPESA_REGISTER_DOCTYPE, "submit_payment"):
				mpesa.submit_payment = 0

			mpesa.flags.ignore_permissions = True
			mpesa.save()
			mpesa.submit()

		if _has_field(MPESA_REGISTER_DOCTYPE, MPESA_SALES_INVOICE_FIELD):
			frappe.db.set_value(MPESA_REGISTER_DOCTYPE, mpesa_name, MPESA_SALES_INVOICE_FIELD, invoice)
		if _has_field(MPESA_REGISTER_DOCTYPE, "pos_invoice"):
			frappe.db.set_value(MPESA_REGISTER_DOCTYPE, mpesa_name, "pos_invoice", invoice)

		processed.append(
			{
				"name": mpesa_name,
				"amount": flt(mpesa.get("transamount") or 0),
				"mode_of_payment": phone_mop,
				"sales_invoice": invoice,
			}
		)

	frappe.db.commit()
	return {"success": True, "processed": processed}


@frappe.whitelist()
def get_stk_payment_match(invoice=None, payment_request=None, phone_number=None, amount=None, company=None, pos_profile=None):
	"""Find the M-Pesa C2B row created after an STK request is paid."""
	if not invoice:
		frappe.throw(_("Sales Invoice is required"))

	if not _doctype_exists(MPESA_REGISTER_DOCTYPE):
		return {"matched": False, "reason": _("M-Pesa payment app is not installed")}

	company = _resolve_company(company=company, pos_profile=pos_profile, invoice=invoice)
	shortcode = _get_mpesa_shortcode_for_company(company)
	if not shortcode:
		return {"matched": False, "reason": _("No Mpesa Settings found for {0}").format(company)}

	amount = flt(amount or 0)
	references = [invoice, payment_request]
	filters = {
		"docstatus": ["!=", 2],
		"businessshortcode": shortcode,
	}

	payments = frappe.get_all(
		MPESA_REGISTER_DOCTYPE,
		filters=filters,
		fields=_build_mpesa_payment_fields(),
		order_by="creation desc",
		limit_page_length=100,
	)

	for payment in payments:
		linked_invoice = payment.get(MPESA_SALES_INVOICE_FIELD) or payment.get("pos_invoice")
		if linked_invoice and linked_invoice != invoice:
			continue

		payment_amount = flt(payment.get("transamount") or 0)
		amount_matches = amount <= 0 or abs(payment_amount - amount) < 0.01
		reference_matches = _reference_matches_payment(payment, references)
		phone_matches = _phone_matches_payment(payment, phone_number)

		score = 0
		reasons = []
		if reference_matches:
			score += 100
			reasons.append(_("Invoice reference"))
		if amount_matches and amount > 0:
			score += 70
			reasons.append(_("Exact amount"))
		if phone_matches:
			score += 20
			reasons.append(_("Same phone"))
		if str(payment.get("posting_date") or "") == nowdate():
			score += 10
			reasons.append(_("Today"))

		if reference_matches or (score >= 90 and amount_matches):
			payment["match_score"] = score
			payment["match_level"] = "High"
			payment["match_reasons"] = reasons
			payment["is_exact_amount"] = amount > 0 and amount_matches
			return {"matched": True, "payment": payment}

	return {"matched": False}


@frappe.whitelist()
def create_payment_request(invoice=None, customer=None, phone_number=None, amount=None):
	"""Create an STK payment request for an existing Sales Invoice."""
	if not invoice or not phone_number or flt(amount) <= 0:
		frappe.throw(_("Sales Invoice, phone number, and amount are required"))

	invoice_doc = frappe.get_doc("Sales Invoice", invoice)

	mpesa_settings = frappe.get_all(
		MPESA_SETTINGS_DOCTYPE,
		filters={"company": invoice_doc.company},
		fields=["name", "payment_gateway_name"],
		limit=1,
	)
	if not mpesa_settings:
		frappe.throw(_("No Mpesa Settings found for {0}").format(invoice_doc.company))

	gateway_name = mpesa_settings[0].get("payment_gateway_name") or mpesa_settings[0].get("name")
	gateway_account = frappe.db.get_value(
		"Payment Gateway Account",
		{"payment_gateway": gateway_name},
		["name", "payment_gateway", "payment_account"],
		as_dict=True,
	)

	if not gateway_account:
		gateway_accounts = frappe.get_all(
			"Payment Gateway Account",
			filters={"payment_gateway": ["like", "%Mpesa%"]},
			fields=["name", "payment_gateway", "payment_account"],
			limit=1,
		)
		if gateway_accounts:
			gateway_account = gateway_accounts[0]

	if not gateway_account:
		frappe.throw(_("No Payment Gateway Account found for Mpesa"))

	phone_mop = _get_phone_mop_for_company(invoice_doc.company)

	payment_request = frappe.new_doc("Payment Request")
	payment_request.payment_request_type = "Inward"
	payment_request.transaction_date = nowdate()
	payment_request.phone_number = phone_number
	payment_request.company = invoice_doc.company
	payment_request.party_type = "Customer"
	payment_request.party = customer or invoice_doc.customer
	payment_request.reference_doctype = "Sales Invoice"
	payment_request.reference_name = invoice
	payment_request.grand_total = flt(amount)
	payment_request.currency = invoice_doc.currency
	payment_request.outstanding_amount = flt(amount)
	payment_request.payment_gateway_account = gateway_account.get("name")
	payment_request.payment_gateway = gateway_account.get("payment_gateway") or gateway_name
	payment_request.payment_account = gateway_account.get("payment_account")
	payment_request.payment_channel = "Phone"
	payment_request.mode_of_payment = phone_mop
	payment_request.subject = _("Payment for {0}").format(invoice)
	payment_request.message = _("Payment for {0}").format(invoice)
	payment_request.mute_email = 1
	payment_request.make_sales_invoice = 0

	payment_request.insert(ignore_permissions=True)
	payment_request.submit()

	return {"success": True, "payment_request": payment_request.name}

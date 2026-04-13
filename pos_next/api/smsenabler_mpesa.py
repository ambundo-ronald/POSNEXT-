# -*- coding: utf-8 -*-
"""SMS Enabler paybill payment inbox for POS Next.

This is intentionally separate from ``pos_next.api.mpesa``. The M-Pesa module
uses the normal M-Pesa C2B register. This module stores raw SMS messages
forwarded by SMS Enabler and exposes them as a separate POS quick-pay source.
"""

from __future__ import unicode_literals

import json
import re

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, nowdate


SMS_REGISTER_DOCTYPE = "SMS Enabler Payment Register"


def _normalize_phone(value):
	return "".join(ch for ch in str(value or "") if ch.isdigit())


def _get_phone_mop_for_company(company):
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


def _get_customer_match_data(customer):
	if not customer:
		return {"phone": "", "name": ""}

	phone = ""
	contact = frappe.db.get_value(
		"Dynamic Link",
		{"link_doctype": "Customer", "link_name": customer, "parenttype": "Contact"},
		"parent",
	)
	if contact:
		phone = frappe.db.get_value("Contact", contact, "mobile_no") or ""
		if not phone:
			phone = frappe.db.get_value("Contact", contact, "phone") or ""

	if not phone:
		phone = frappe.db.get_value("Customer", customer, "mobile_no") or ""

	customer_name = frappe.db.get_value("Customer", customer, "customer_name") or customer
	return {"phone": _normalize_phone(phone), "name": str(customer_name or "").lower()}


def _parse_amount(message):
	patterns = [
		r"(?:KES|KSH|Ksh|Kes)\s*([0-9][0-9,]*(?:\.\d{1,2})?)",
		r"([0-9][0-9,]*(?:\.\d{1,2})?)\s*(?:KES|KSH|Ksh|Kes)",
	]
	for pattern in patterns:
		match = re.search(pattern, message or "", re.IGNORECASE)
		if match:
			return flt(match.group(1).replace(",", ""))
	return 0


def _parse_transaction_id(message):
	patterns = [
		r"\b(?:transaction|trans|txn|tx|ref|reference)\s*(?:id|no|number|code)?[:\s#-]*([A-Z0-9]{6,})",
		r"\b([A-Z0-9]{8,})\b",
	]
	for pattern in patterns:
		match = re.search(pattern, message or "", re.IGNORECASE)
		if match:
			return match.group(1).upper()
	return None


def _parse_account_reference(message):
	patterns = [
		r"\b(?:account|acc|a/c|reference|ref)\s*(?:no|number)?[:\s#-]*([A-Z0-9\-_/]{3,})",
		r"\b(?:for|to)\s+account\s+([A-Z0-9\-_/]{3,})",
	]
	for pattern in patterns:
		match = re.search(pattern, message or "", re.IGNORECASE)
		if match:
			return match.group(1).upper()
	return None


def _parse_payer_phone(message):
	match = re.search(r"(?:254|0)7\d{8}", message or "")
	return match.group(0) if match else None


def _parse_payer_name(message):
	match = re.search(r"\bfrom\s+([A-Z][A-Z\s.'-]{2,40})(?:\s+\d|\s+on|\s+for|\.|,)", message or "", re.IGNORECASE)
	if match:
		return " ".join(match.group(1).split()).title()
	return None


def parse_sms_message(message, sender=None, source=None):
	source = source or sender or "SMS Enabler"
	amount = _parse_amount(message)
	transaction_id = _parse_transaction_id(message)

	return {
		"source": source,
		"transaction_id": transaction_id,
		"amount": amount,
		"payer_name": _parse_payer_name(message),
		"payer_phone": _parse_payer_phone(message),
		"account_reference": _parse_account_reference(message),
		"parse_status": "Parsed" if amount and transaction_id else "Partial",
		"parse_error": "" if amount and transaction_id else "Could not confidently parse amount and transaction ID",
	}


def _score_payment_match(payment, amount=0, customer_data=None):
	score = 0
	reasons = []
	amount = flt(amount or 0)
	customer_data = customer_data or {}
	payment_amount = flt(payment.get("amount") or 0)

	if amount > 0:
		difference = abs(payment_amount - amount)
		if difference < 0.01:
			score += 70
			reasons.append(_("Exact amount"))
		elif difference <= max(1, amount * 0.02):
			score += 35
			reasons.append(_("Close amount"))

	customer_phone = customer_data.get("phone")
	payment_phone = _normalize_phone(payment.get("payer_phone"))
	if customer_phone and payment_phone:
		if payment_phone.endswith(customer_phone[-9:]) or customer_phone.endswith(payment_phone[-9:]):
			score += 25
			reasons.append(_("Same phone"))

	customer_name = customer_data.get("name")
	payment_name = str(payment.get("payer_name") or "").lower()
	if customer_name and payment_name:
		customer_tokens = {token for token in customer_name.split() if len(token) >= 3}
		payment_tokens = {token for token in payment_name.split() if len(token) >= 3}
		if customer_tokens and customer_tokens.intersection(payment_tokens):
			score += 10
			reasons.append(_("Name match"))

	if str(payment.get("received_at") or "").startswith(nowdate()):
		score += 10
		reasons.append(_("Today"))

	if payment.get("account_reference"):
		score += 5
		reasons.append(_("Has reference"))

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


def _parse_payment_names(payments):
	if isinstance(payments, str):
		try:
			payments = json.loads(payments)
		except ValueError:
			payments = [p.strip() for p in payments.split(",") if p.strip()]

	names = []
	for payment in payments or []:
		if isinstance(payment, dict):
			name = payment.get("name") or payment.get("sms_payment_name")
		else:
			name = payment
		if name:
			names.append(str(name).strip())
	return names


@frappe.whitelist()
def check_sms_enabler_available(company=None, pos_profile=None):
	if pos_profile and not company:
		company = frappe.db.get_value("POS Profile", pos_profile, "company")

	return {
		"available": True,
		"mode_of_payment": _get_phone_mop_for_company(company),
		"company": company,
	}


@frappe.whitelist(allow_guest=True)
def receive_sms(sender=None, message=None, received_at=None, source=None, company=None, token=None):
	"""HTTP endpoint for SMS Enabler to forward incoming SMS messages."""
	expected_token = frappe.conf.get("sms_enabler_token")
	if expected_token and token != expected_token:
		frappe.throw(_("Invalid SMS Enabler token"), frappe.PermissionError)

	message = message or frappe.form_dict.get("text") or frappe.form_dict.get("message")
	sender = sender or frappe.form_dict.get("sender") or frappe.form_dict.get("from")
	if not message:
		frappe.throw(_("SMS message is required"))

	parsed = parse_sms_message(message, sender=sender, source=source)

	doc = frappe.new_doc(SMS_REGISTER_DOCTYPE)
	doc.sender = sender
	doc.raw_message = message
	doc.received_at = received_at or now_datetime()
	doc.company = company
	doc.status = "Pending" if parsed.get("parse_status") == "Parsed" else "Failed Parse"
	doc.update(parsed)
	doc.insert(ignore_permissions=True)

	return {"success": True, "payment": doc.name, "status": doc.status}


@frappe.whitelist()
def get_sms_payments(company=None, pos_profile=None, search=None, amount=None, customer=None):
	search = (search or "").strip()
	amount = flt(amount or 0)
	if pos_profile and not company:
		company = frappe.db.get_value("POS Profile", pos_profile, "company")

	filters = {"status": "Pending"}
	if company:
		filters["company"] = ["in", [company, "", None]]

	total_count = frappe.db.count(SMS_REGISTER_DOCTYPE, filters)
	if len(search) < 3 and amount <= 0:
		return {"count": total_count, "payments": []}

	payments = frappe.get_all(
		SMS_REGISTER_DOCTYPE,
		filters=filters,
		fields=[
			"name",
			"source",
			"sender",
			"transaction_id",
			"amount",
			"payer_name",
			"payer_phone",
			"account_reference",
			"received_at",
			"raw_message",
			"mode_of_payment",
		],
		order_by="received_at desc",
		limit_page_length=100,
	)

	search_lower = search.lower()
	customer_data = _get_customer_match_data(customer)
	matches = []
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
		search_match = len(search) >= 3 and any(search_lower in str(value or "").lower() for value in values)
		scored_payment = _score_payment_match(payment, amount=amount, customer_data=customer_data)
		if search_match or (amount > 0 and scored_payment.get("match_score", 0) > 0):
			matches.append(scored_payment)

	matches.sort(
		key=lambda item: (
			item.get("match_score", 0),
			item.get("is_exact_amount", False),
			str(item.get("received_at") or ""),
		),
		reverse=True,
	)
	return {"count": total_count, "payments": matches}


@frappe.whitelist()
def process_sales_invoice_payments(invoice=None, customer=None, company=None, sms_payments=None):
	if not invoice:
		frappe.throw(_("Sales Invoice is required"))
	if not frappe.db.exists("Sales Invoice", invoice):
		frappe.throw(_("Sales Invoice {0} does not exist").format(invoice))

	invoice_doc = frappe.get_doc("Sales Invoice", invoice)
	company = company or invoice_doc.company
	mode_of_payment = _get_phone_mop_for_company(company)
	names = _parse_payment_names(sms_payments)
	if not names:
		frappe.throw(_("No SMS Enabler payments selected"))

	processed = []
	for name in names:
		payment = frappe.get_doc(SMS_REGISTER_DOCTYPE, name)
		if payment.status not in ("Pending", "Matched"):
			frappe.throw(_("SMS payment {0} is already {1}").format(name, payment.status))

		payment.customer = customer or invoice_doc.customer
		payment.company = company
		payment.sales_invoice = invoice
		payment.mode_of_payment = payment.mode_of_payment or mode_of_payment
		payment.status = "Consumed"
		payment.flags.ignore_permissions = True
		payment.save()

		processed.append(
			{
				"name": name,
				"amount": flt(payment.amount),
				"mode_of_payment": payment.mode_of_payment,
				"sales_invoice": invoice,
			}
		)

	return {"success": True, "processed": processed}

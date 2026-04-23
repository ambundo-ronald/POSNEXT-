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
from frappe.utils import flt, getdate, now_datetime, nowdate

from pos_next.pos_next.doctype.pos_settings.pos_settings import (
	get_global_sms_enabler_settings,
)


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

	fallback_mop = None
	for mop in phone_mops:
		account = frappe.db.get_value(
			"Mode of Payment Account",
			{"parent": mop.name, "company": company},
			"default_account",
		)
		if not account:
			continue

		account_type = frappe.db.get_value("Account", account, "account_type")
		if account_type in ("Cash", "Bank"):
			return mop.name

		if not fallback_mop:
			fallback_mop = mop.name

	return fallback_mop


def _get_sms_enabler_settings(pos_profile=None):
	settings = frappe._dict(get_global_sms_enabler_settings())
	if not settings.get("sms_enabler_enabled"):
		return None

	settings["pos_profile"] = pos_profile
	settings["company"] = (
		frappe.db.get_value("POS Profile", pos_profile, "company")
		if pos_profile
		else None
	)
	return settings


def _resolve_mapped_mode_of_payment(sender=None, source=None, message=None, settings=None):
	settings = settings or frappe._dict(get_global_sms_enabler_settings())
	search_text = "\n".join(str(value or "") for value in (sender, source, message)).lower()

	for mapping in settings.get("sms_enabler_sender_mappings") or []:
		if not mapping.get("enabled", 1):
			continue

		match_text = str(mapping.get("match_text") or "").strip().lower()
		mode_of_payment = mapping.get("mode_of_payment")
		if match_text and mode_of_payment and match_text in search_text:
			return mode_of_payment

	return None


def _get_sms_enabler_settings_by_token(token):
	if not token:
		return None

	global_settings = frappe._dict(get_global_sms_enabler_settings())
	if (
		global_settings.get("sms_enabler_enabled")
		and global_settings.get("sms_enabler_token")
		and token == global_settings.get("sms_enabler_token")
	):
		return global_settings

	# Backward compatibility for sites that still have SMS Enabler configured on
	# an older POS Settings record.
	settings = frappe.db.get_value(
		"POS Settings",
		{"enabled": 1, "sms_enabler_enabled": 1, "sms_enabler_token": token},
		[
			"name",
			"pos_profile",
			"sms_enabler_enabled",
			"sms_enabler_token",
			"sms_enabler_source",
		],
		as_dict=True,
	)
	if not settings:
		return None

	settings["company"] = frappe.db.get_value("POS Profile", settings.pos_profile, "company")
	return settings


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
		r"\b(?:KES|KSH)\.?\s*([0-9][0-9,]*(?:\.\d{1,2})?)",
		r"\b([0-9][0-9,]*(?:\.\d{1,2})?)\s*(?:KES|KSH)\.?\b",
	]
	for pattern in patterns:
		match = re.search(pattern, message or "", re.IGNORECASE)
		if match:
			return flt(match.group(1).replace(",", ""))
	return 0


def _parse_transaction_id(message):
	patterns = [
		r"\b(?:M[\s-]?PESA|MPESA)\s+Ref\.?\s*[:#-]?\s*([A-Z0-9]{6,})",
		r"\b(?:transaction|trans|txn|tx|ref|reference)\s*(?:id|no|number|code)?[:.\s#-]*([A-Z0-9]{6,})",
		r"\b([A-Z0-9]{8,})\b",
	]
	for pattern in patterns:
		match = re.search(pattern, message or "", re.IGNORECASE)
		if match:
			return match.group(1).upper()
	return None


def _parse_account_reference(message):
	patterns = [
		r"\b(?:A/C|account|acc)\s+(?:ref\.?\s*)?(?:no|number)?\.?[:\s#-]*([A-Z0-9\-_/]{3,})",
		r"\bfor\s+([A-Z0-9\-_/]{3,})\s+has\s+been\s+received\b",
		r"\b(?:for|to)\s+account\s+([A-Z0-9\-_/]{3,})",
	]
	for pattern in patterns:
		match = re.search(pattern, message or "", re.IGNORECASE)
		if match:
			return match.group(1).upper()
	return None


def _parse_payer_phone(message):
	patterns = [
		r"(?:254|0)7\d{8}",
		r"\b0?7[0-9*]{2,7}\d{2,3}\b",
	]
	for pattern in patterns:
		match = re.search(pattern, message or "")
		if match:
			return match.group(0)
	return None


def _parse_payer_name(message):
	patterns = [
		r"\bfrom\s+([A-Z][A-Z\s.'-]{2,80}?)(?:\s+\d|\s+on|\s+for|\.|,)",
		r"\bby\s+([A-Z][A-Z\s.'-]{2,80}?)(?:\s+phone\b|\s+on\b|\.|,)",
	]
	for pattern in patterns:
		match = re.search(pattern, message or "", re.IGNORECASE)
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


def _find_payment_entry_for_sms(invoice, transaction_id=None, amount=None):
	if not invoice:
		return None

	conditions = ["pe.docstatus = 1", "pe.payment_type = 'Receive'", "per.reference_name = %(invoice)s"]
	params = {"invoice": invoice}

	if transaction_id:
		conditions.append("pe.reference_no = %(transaction_id)s")
		params["transaction_id"] = transaction_id

	if amount:
		conditions.append("ABS(pe.paid_amount - %(amount)s) < 0.01")
		params["amount"] = flt(amount)

	result = frappe.db.sql(
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
	return result[0].name if result else None


def _has_invoice_access(invoice_doc, permtype="read"):
	if frappe.has_permission("Sales Invoice", permtype, invoice_doc.name):
		return True

	pos_profile = invoice_doc.get("pos_profile")
	if not pos_profile:
		return False

	return bool(
		frappe.db.exists(
			"POS Profile User",
			{"parent": pos_profile, "user": frappe.session.user},
		)
	)


@frappe.whitelist()
def check_sms_enabler_available(company=None, pos_profile=None):
	if pos_profile and not company:
		company = frappe.db.get_value("POS Profile", pos_profile, "company")

	settings = _get_sms_enabler_settings(pos_profile) if pos_profile else None
	if pos_profile and not (settings and settings.get("sms_enabler_enabled")):
		return {
			"available": False,
			"reason": _("SMS Enabler is not enabled in POS Next Global Settings"),
			"mode_of_payment": None,
			"company": company,
		}

	mode_of_payment = _get_phone_mop_for_company(company)
	if not mode_of_payment:
		return {
			"available": False,
			"reason": _("No enabled Phone mode of payment is configured for this company"),
			"mode_of_payment": None,
			"company": company,
		}

	return {
		"available": True,
		"mode_of_payment": mode_of_payment,
		"company": company,
	}


@frappe.whitelist(allow_guest=True)
def receive_sms(sender=None, message=None, received_at=None, source=None, company=None, token=None):
	"""HTTP endpoint for SMS Enabler to forward incoming SMS messages."""
	token = (
		token
		or frappe.form_dict.get("token")
		or frappe.form_dict.get("tag")
		or frappe.get_request_header("X-SMS-Enabler-Token")
		or frappe.get_request_header("X-SMS-Token")
	)
	expected_token = frappe.conf.get("sms_enabler_token")
	settings = None
	if expected_token:
		if token != expected_token:
			settings = _get_sms_enabler_settings_by_token(token)
			if not settings:
				frappe.throw(_("Invalid SMS Enabler token"), frappe.PermissionError)
	else:
		settings = _get_sms_enabler_settings_by_token(token)
		if not settings:
			global_settings = get_global_sms_enabler_settings()
			legacy_configured_count = frappe.db.count(
				"POS Settings",
				{"enabled": 1, "sms_enabler_enabled": 1},
			)
			if global_settings.get("sms_enabler_enabled") or legacy_configured_count:
				frappe.throw(_("Invalid SMS Enabler token"), frappe.PermissionError)

	if settings:
		company = company or settings.get("company")
		source = source or settings.get("sms_enabler_source")

	message = message or frappe.form_dict.get("text") or frappe.form_dict.get("message")
	sender = sender or frappe.form_dict.get("sender") or frappe.form_dict.get("from")
	received_at = received_at or frappe.form_dict.get("scts")
	if not message:
		frappe.throw(_("SMS message is required"))

	parsed = parse_sms_message(message, sender=sender, source=source)
	mapped_mode_of_payment = _resolve_mapped_mode_of_payment(
		sender=sender,
		source=source,
		message=message,
		settings=settings,
	)

	doc = frappe.new_doc(SMS_REGISTER_DOCTYPE)
	doc.sender = sender
	doc.raw_message = message
	doc.received_at = received_at or now_datetime()
	doc.company = company
	doc.mode_of_payment = mapped_mode_of_payment
	doc.status = "Pending" if parsed.get("parse_status") == "Parsed" else "Failed Parse"
	doc.update(parsed)
	doc.insert(ignore_permissions=True)

	return {"success": True, "payment": doc.name, "status": doc.status}


@frappe.whitelist()
def reparse_sms_payment(name):
	"""Reparse a saved SMS Enabler payment register record from raw_message."""
	if not name:
		frappe.throw(_("SMS payment record is required"))

	doc = frappe.get_doc(SMS_REGISTER_DOCTYPE, name)
	if not doc.has_permission("write"):
		frappe.throw(_("You don't have permission to reparse this SMS payment"), frappe.PermissionError)

	if doc.status == "Consumed" or doc.payment_entry:
		frappe.throw(_("Consumed SMS payments cannot be reparsed"))

	if not doc.raw_message:
		frappe.throw(_("Raw SMS message is required"))

	parsed = parse_sms_message(
		doc.raw_message,
		sender=doc.sender,
		source=doc.source,
	)
	mapped_mode_of_payment = _resolve_mapped_mode_of_payment(
		sender=doc.sender,
		source=doc.source,
		message=doc.raw_message,
	)

	for field in (
		"source",
		"transaction_id",
		"amount",
		"payer_name",
		"payer_phone",
		"account_reference",
		"parse_status",
		"parse_error",
	):
		doc.set(field, parsed.get(field))

	if mapped_mode_of_payment:
		doc.mode_of_payment = mapped_mode_of_payment

	if parsed.get("parse_status") == "Parsed":
		if doc.status in ("Failed Parse", "Duplicate") or not doc.sales_invoice:
			doc.status = "Pending"
	else:
		if doc.status != "Matched":
			doc.status = "Failed Parse"

	doc.save()

	return {
		"success": True,
		"name": doc.name,
		"status": doc.status,
		"parse_status": doc.parse_status,
		"parse_error": doc.parse_error,
		"transaction_id": doc.transaction_id,
		"amount": doc.amount,
		"payer_name": doc.payer_name,
		"payer_phone": doc.payer_phone,
		"account_reference": doc.account_reference,
	}


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
		search_match = not search or any(search_lower in str(value or "").lower() for value in values)
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
def get_sms_payments_for_payment_reconciliation(company=None, party_type=None, party=None, search=None):
	if party_type and party_type != "Customer":
		return {"count": 0, "payments": []}

	customer = party if party_type == "Customer" else None
	result = get_sms_payments(company=company, search=search, customer=customer)
	formatted_payments = []

	for payment in result.get("payments") or []:
		reference_name = payment.get("transaction_id") or payment.get("name")
		received_at = payment.get("received_at")
		posting_date = getdate(received_at) if received_at else None
		reference_type = payment.get("sender") or payment.get("source") or _("SMS Enabler")

		formatted_payments.append(
			{
				"name": payment.get("name"),
				"sms_payment": payment.get("name"),
				"reference_name": reference_name,
				"posting_date": posting_date,
				"amount": flt(payment.get("amount")),
				"reference_type": reference_type,
				"sender": payment.get("sender"),
				"source": payment.get("source"),
				"payer_name": payment.get("payer_name"),
				"payer_phone": payment.get("payer_phone"),
				"account_reference": payment.get("account_reference"),
				"received_at": received_at,
				"match_score": payment.get("match_score", 0),
				"match_level": payment.get("match_level"),
			}
		)

	result["payments"] = formatted_payments
	return result


@frappe.whitelist()
def get_sms_payment_matches_for_invoice(invoice=None, search=None):
	if not invoice:
		frappe.throw(_("Sales Invoice is required"))
	if not frappe.db.exists("Sales Invoice", invoice):
		frappe.throw(_("Sales Invoice {0} does not exist").format(invoice))

	invoice_doc = frappe.get_doc("Sales Invoice", invoice)
	if not _has_invoice_access(invoice_doc, "read"):
		frappe.throw(_("You don't have permission to view this invoice"), frappe.PermissionError)
	if invoice_doc.docstatus != 1:
		frappe.throw(_("Only submitted invoices can be reconciled"))
	if invoice_doc.is_return:
		frappe.throw(_("Return invoices cannot be reconciled from SMS Enabler payments"))

	outstanding = flt(invoice_doc.outstanding_amount)
	if outstanding <= 0:
		return {"count": 0, "payments": [], "outstanding_amount": outstanding}

	result = get_sms_payments(
		company=invoice_doc.company,
		pos_profile=invoice_doc.pos_profile,
		search=search,
		amount=outstanding,
		customer=invoice_doc.customer,
	)
	result["invoice"] = invoice_doc.name
	result["outstanding_amount"] = outstanding
	return result


@frappe.whitelist()
def reconcile_invoice_with_sms_payments(invoice=None, sms_payments=None):
	if not invoice:
		frappe.throw(_("Sales Invoice is required"))
	if not frappe.db.exists("Sales Invoice", invoice):
		frappe.throw(_("Sales Invoice {0} does not exist").format(invoice))

	invoice_doc = frappe.get_doc("Sales Invoice", invoice)
	if not _has_invoice_access(invoice_doc, "read"):
		frappe.throw(_("You don't have permission to view this invoice"), frappe.PermissionError)
	if invoice_doc.docstatus != 1:
		frappe.throw(_("Only submitted invoices can be reconciled"))
	if invoice_doc.is_return:
		frappe.throw(_("Return invoices cannot be reconciled from SMS Enabler payments"))

	names = _parse_payment_names(sms_payments)
	if not names:
		frappe.throw(_("No SMS Enabler payments selected"))

	outstanding = flt(invoice_doc.outstanding_amount)
	if outstanding <= 0:
		frappe.throw(_("Invoice {0} is already fully paid").format(invoice))

	mode_of_payment = _get_phone_mop_for_company(invoice_doc.company)
	payments_to_create = []
	selected_payments = []
	linked_entries = {}

	for name in names:
		payment = frappe.get_doc(SMS_REGISTER_DOCTYPE, name)
		if payment.status not in ("Pending", "Matched"):
			frappe.throw(_("SMS payment {0} is already {1}").format(name, payment.status))
		if payment.company and payment.company != invoice_doc.company:
			frappe.throw(_("SMS payment {0} belongs to company {1}").format(name, payment.company))

		amount = flt(payment.amount)
		if amount <= 0:
			frappe.throw(_("SMS payment {0} has no valid amount").format(name))

		selected_mode = payment.mode_of_payment or mode_of_payment
		if not selected_mode:
			frappe.throw(_("No enabled Phone mode of payment is configured for company {0}").format(invoice_doc.company))

		existing_payment_entry = payment.payment_entry or _find_payment_entry_for_sms(
			invoice,
			transaction_id=payment.transaction_id,
			amount=amount,
		)

		selected_payments.append((payment, selected_mode))
		if existing_payment_entry:
			linked_entries[name] = existing_payment_entry
			continue

		payments_to_create.append(
			{
				"name": name,
				"payload": {
					"mode_of_payment": selected_mode,
					"amount": amount,
					"reference_no": payment.transaction_id or payment.name,
				},
			}
		)

	total_new_amount = sum(flt(item["payload"]["amount"]) for item in payments_to_create)
	if total_new_amount > outstanding + 0.01:
		frappe.throw(
			_("Selected payment amount {0} exceeds outstanding amount {1}").format(
				frappe.format_value(total_new_amount, {"fieldtype": "Currency"}),
				frappe.format_value(outstanding, {"fieldtype": "Currency"}),
			)
		)

	payment_entries_created = []
	if payments_to_create:
		from pos_next.api.partial_payments import add_payment_to_partial_invoice

		result = add_payment_to_partial_invoice(
			invoice,
			[item["payload"] for item in payments_to_create],
		)
		payment_entries_created = result.get("payment_entries_created") or []

		for item, payment_entry in zip(payments_to_create, payment_entries_created):
			linked_entries[item["name"]] = payment_entry

	processed = []
	for payment, selected_mode in selected_payments:
		payment.customer = invoice_doc.customer
		payment.company = invoice_doc.company
		payment.sales_invoice = invoice
		payment.mode_of_payment = selected_mode
		payment.payment_entry = linked_entries.get(payment.name) or payment.payment_entry
		payment.status = "Consumed"
		payment.flags.ignore_permissions = True
		payment.save()

		processed.append(
			{
				"name": payment.name,
				"amount": flt(payment.amount),
				"mode_of_payment": payment.mode_of_payment,
				"sales_invoice": invoice,
				"payment_entry": payment.payment_entry,
			}
		)

	invoice_doc.reload()
	return {
		"success": True,
		"invoice": invoice,
		"status": invoice_doc.status,
		"paid_amount": flt(invoice_doc.paid_amount),
		"outstanding_amount": flt(invoice_doc.outstanding_amount),
		"payment_entries_created": payment_entries_created,
		"processed": processed,
	}


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

	selected_total = 0
	for name in names:
		selected_total += flt(
			frappe.db.get_value(SMS_REGISTER_DOCTYPE, name, "amount") or 0
		)

	# POS checkout normally includes SMS selections as direct Sales Invoice payment rows.
	# If the invoice still shows less paid than the selected SMS total, fall back to the
	# reconciliation path so the invoice is actually settled before the SMS rows are consumed.
	if (
		invoice_doc.docstatus == 1
		and selected_total > flt(invoice_doc.paid_amount) + 0.01
		and flt(invoice_doc.outstanding_amount) > 0.01
	):
		return reconcile_invoice_with_sms_payments(invoice=invoice, sms_payments=names)

	processed = []
	for name in names:
		payment = frappe.get_doc(SMS_REGISTER_DOCTYPE, name)
		if payment.status not in ("Pending", "Matched"):
			frappe.throw(_("SMS payment {0} is already {1}").format(name, payment.status))

		payment.customer = customer or invoice_doc.customer
		payment.company = company
		payment.sales_invoice = invoice
		payment.mode_of_payment = payment.mode_of_payment or mode_of_payment
		payment.payment_entry = payment.payment_entry or _find_payment_entry_for_sms(
			invoice,
			transaction_id=payment.transaction_id,
			amount=payment.amount,
		)
		payment.status = "Consumed"
		payment.flags.ignore_permissions = True
		payment.save()

		processed.append(
			{
				"name": name,
				"amount": flt(payment.amount),
				"mode_of_payment": payment.mode_of_payment,
				"sales_invoice": invoice,
				"payment_entry": payment.payment_entry,
			}
		)

	return {"success": True, "processed": processed}

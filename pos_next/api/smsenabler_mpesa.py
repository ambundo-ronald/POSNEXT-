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
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from pos_next.pos_next.doctype.pos_settings.pos_settings import (
	_serialize_sms_sender_mappings,
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
	global_settings = frappe._dict(get_global_sms_enabler_settings())
	if global_settings.get("sms_enabler_enabled"):
		global_settings["pos_profile"] = pos_profile
		global_settings["company"] = (
			frappe.db.get_value("POS Profile", pos_profile, "company")
			if pos_profile
			else None
		)
		global_settings["sms_enabler_is_global"] = 1
		return global_settings

	if not pos_profile:
		return None

	name = frappe.db.get_value(
		"POS Settings",
		{"pos_profile": pos_profile, "enabled": 1, "sms_enabler_enabled": 1},
		"name",
	)
	if not name:
		return None

	doc = frappe.get_doc("POS Settings", name)
	return frappe._dict(
		{
			"name": doc.name,
			"pos_profile": doc.pos_profile,
			"company": frappe.db.get_value("POS Profile", doc.pos_profile, "company"),
			"sms_enabler_enabled": cint(doc.sms_enabler_enabled),
			"sms_enabler_token": doc.sms_enabler_token,
			"sms_enabler_source": doc.sms_enabler_source or "SMS Enabler",
			"sms_enabler_sender_mappings": _serialize_sms_sender_mappings(doc),
			"sms_enabler_is_global": 0,
		}
	)


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
		global_settings["sms_enabler_is_global"] = 1
		return global_settings

	# Profile tokens become authoritative only after shared global mode is disabled.
	if global_settings.get("sms_enabler_enabled"):
		return None

	matches = frappe.get_all(
		"POS Settings",
		filters={"enabled": 1, "sms_enabler_enabled": 1, "sms_enabler_token": token},
		fields=[
			"name",
			"pos_profile",
			"sms_enabler_enabled",
			"sms_enabler_token",
			"sms_enabler_source",
		],
		limit_page_length=2,
	)
	if len(matches) != 1:
		return None

	settings = frappe._dict(matches[0])
	doc = frappe.get_doc("POS Settings", settings.name)
	settings["company"] = frappe.db.get_value("POS Profile", settings.pos_profile, "company")
	settings["sms_enabler_sender_mappings"] = _serialize_sms_sender_mappings(doc)
	settings["sms_enabler_is_global"] = 0
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
	payment_amount = flt(payment.get("available_amount") or payment.get("amount") or 0)

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


def _parse_payment_allocations(payments):
	if isinstance(payments, str):
		try:
			payments = json.loads(payments)
		except ValueError:
			payments = [p.strip() for p in payments.split(",") if p.strip()]

	allocations = []
	for payment in payments or []:
		if isinstance(payment, dict):
			name = payment.get("name") or payment.get("sms_payment_name")
			amount = flt(payment.get("amount") or 0)
		else:
			name = payment
			amount = 0
		if name:
			allocations.append({"name": str(name).strip(), "amount": amount})
	return allocations


def _get_sms_payment_amounts(payment):
	total = flt(payment.get("amount"))
	allocated = max(flt(payment.get("allocated_amount")), 0)
	available = max(total - allocated, 0)
	return total, allocated, available


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


def _create_sms_payment_entry(payment, invoice_doc, allocated_amount, mode_of_payment):
	from pos_next.api.partial_payments import _resolve_payment_account

	total_amount, _allocated_amount, _available_amount = _get_sms_payment_amounts(payment)
	posting_date = max(
		getdate(payment.received_at) if payment.received_at else getdate(nowdate()),
		getdate(invoice_doc.posting_date),
	)

	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = "Receive"
	pe.posting_date = posting_date
	pe.party_type = "Customer"
	pe.party = invoice_doc.customer
	pe.company = invoice_doc.company
	pe.mode_of_payment = mode_of_payment
	pe.paid_from = invoice_doc.debit_to
	pe.paid_to = _resolve_payment_account(
		mode_of_payment=mode_of_payment,
		company=invoice_doc.company,
		invoice=invoice_doc,
	)
	pe.paid_amount = total_amount
	pe.received_amount = total_amount
	pe.paid_from_account_currency = invoice_doc.currency
	pe.paid_to_account_currency = invoice_doc.currency
	pe.reference_no = (payment.transaction_id or payment.name)[:140]
	pe.reference_date = posting_date
	pe.remarks = _("SMS Enabler reconciliation for {0}").format(payment.name)
	pe.append(
		"references",
		{
			"reference_doctype": "Sales Invoice",
			"reference_name": invoice_doc.name,
			"total_amount": invoice_doc.grand_total,
			"outstanding_amount": invoice_doc.outstanding_amount,
			"allocated_amount": allocated_amount,
		},
	)
	pe.flags.ignore_permissions = True
	pe.insert()
	pe.submit()
	return pe.name


def _create_sms_advance_payment_entry(payment, invoice_doc, amount, mode_of_payment):
	from pos_next.api.partial_payments import _resolve_payment_account

	posting_date = max(
		getdate(payment.received_at) if payment.received_at else getdate(nowdate()),
		getdate(invoice_doc.posting_date),
	)
	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = "Receive"
	pe.posting_date = posting_date
	pe.party_type = "Customer"
	pe.party = invoice_doc.customer
	pe.company = invoice_doc.company
	pe.mode_of_payment = mode_of_payment
	pe.paid_from = invoice_doc.debit_to
	pe.paid_to = _resolve_payment_account(
		mode_of_payment=mode_of_payment,
		company=invoice_doc.company,
		invoice=invoice_doc,
	)
	pe.paid_amount = amount
	pe.received_amount = amount
	pe.paid_from_account_currency = invoice_doc.currency
	pe.paid_to_account_currency = invoice_doc.currency
	pe.reference_no = (payment.transaction_id or payment.name)[:140]
	pe.reference_date = posting_date
	pe.remarks = _("Unallocated SMS Enabler balance for {0}").format(payment.name)
	pe.flags.ignore_permissions = True
	pe.insert()
	pe.submit()
	return pe.name


def _allocate_existing_payment_entry(payment_entry, invoice_doc, allocated_amount):
	from erpnext.accounts.utils import reconcile_against_document

	pe = frappe.get_doc("Payment Entry", payment_entry)
	if pe.docstatus != 1:
		frappe.throw(_("Payment Entry {0} is not submitted").format(pe.name))
	if pe.party_type != "Customer" or pe.party != invoice_doc.customer:
		frappe.throw(
			_("SMS payment credit belongs to customer {0}, not {1}").format(
				pe.party, invoice_doc.customer
			)
		)
	if pe.company != invoice_doc.company:
		frappe.throw(_("Payment Entry {0} belongs to company {1}").format(pe.name, pe.company))

	reconcile_against_document(
		[
			frappe._dict(
				{
					"voucher_type": "Payment Entry",
					"voucher_no": pe.name,
					"voucher_detail_no": None,
					"against_voucher_type": "Sales Invoice",
					"against_voucher": invoice_doc.name,
					"account": pe.paid_from,
					"exchange_rate": pe.source_exchange_rate or 1,
					"grand_total": invoice_doc.grand_total,
					"outstanding_amount": invoice_doc.outstanding_amount,
					"dimensions": {},
					"party_type": "Customer",
					"party": invoice_doc.customer,
					"is_advance": pe.get("book_advance_payments_in_separate_party_account"),
					"dr_or_cr": "credit_in_account_currency",
					"unreconciled_amount": flt(pe.unallocated_amount),
					"unadjusted_amount": flt(pe.unallocated_amount),
					"allocated_amount": allocated_amount,
					"difference_amount": 0,
					"difference_account": None,
					"difference_posting_date": None,
				}
			)
		]
	)
	return pe.name


def _apply_sms_payment_to_invoice(payment, invoice_doc, requested_amount=0):
	total_amount, allocated_amount, available_amount = _get_sms_payment_amounts(payment)
	if total_amount <= 0 or available_amount <= 0.01:
		frappe.throw(_("SMS payment {0} has no available balance").format(payment.name))
	if payment.customer and payment.customer != invoice_doc.customer:
		frappe.throw(
			_("SMS payment {0} is already linked to customer {1}").format(
				payment.name, payment.customer
			)
		)

	invoice_outstanding = flt(invoice_doc.outstanding_amount)
	to_allocate = min(available_amount, invoice_outstanding)
	if requested_amount > 0:
		to_allocate = min(to_allocate, flt(requested_amount))
	if to_allocate <= 0.01:
		frappe.throw(_("There is no amount available to allocate"))

	mode_of_payment = payment.mode_of_payment or _get_phone_mop_for_company(invoice_doc.company)
	if not mode_of_payment:
		frappe.throw(
			_("No enabled Phone mode of payment is configured for company {0}").format(
				invoice_doc.company
			)
		)

	if payment.payment_entry:
		payment_entry = _allocate_existing_payment_entry(
			payment.payment_entry, invoice_doc, to_allocate
		)
	else:
		payment_entry = _create_sms_payment_entry(
			payment, invoice_doc, to_allocate, mode_of_payment
		)

	new_allocated = min(allocated_amount + to_allocate, total_amount)
	new_available = max(total_amount - new_allocated, 0)
	payment.customer = invoice_doc.customer
	payment.company = invoice_doc.company
	payment.pos_profile = payment.pos_profile or invoice_doc.pos_profile
	payment.sales_invoice = invoice_doc.name
	payment.mode_of_payment = mode_of_payment
	payment.payment_entry = payment_entry
	payment.allocated_amount = new_allocated
	payment.available_amount = new_available
	payment.status = "Consumed" if new_available <= 0.01 else "Partially Allocated"
	payment.flags.ignore_permissions = True
	payment.save()

	return {
		"name": payment.name,
		"original_amount": total_amount,
		"allocated_now": to_allocate,
		"allocated_amount": new_allocated,
		"available_amount": new_available,
		"mode_of_payment": mode_of_payment,
		"sales_invoice": invoice_doc.name,
		"payment_entry": payment_entry,
		"status": payment.status,
	}


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
			"reason": _("SMS Enabler is not enabled for this POS Profile"),
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
	global_settings = get_global_sms_enabler_settings()
	expected_token = (
		frappe.conf.get("sms_enabler_token")
		if global_settings.get("sms_enabler_enabled")
		else None
	)
	settings = None
	if expected_token:
		if token == expected_token:
			settings = frappe._dict(global_settings)
			settings["sms_enabler_is_global"] = 1
		else:
			settings = _get_sms_enabler_settings_by_token(token)
			if not settings:
				frappe.throw(_("Invalid SMS Enabler token"), frappe.PermissionError)
	else:
		settings = _get_sms_enabler_settings_by_token(token)
		if not settings:
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
	doc.pos_profile = settings.get("pos_profile") if settings else None
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
def recheck_duplicate_sms_payments(sender=None, company=None, limit=500):
	"""Re-evaluate duplicate SMS payment rows after duplicate rules change."""
	filters = {"status": "Duplicate"}
	if sender:
		filters["sender"] = sender
	if company:
		filters["company"] = company

	rows = frappe.get_all(
		SMS_REGISTER_DOCTYPE,
		filters=filters,
		fields=["name"],
		order_by="received_at desc",
		limit_page_length=limit,
	)

	updated = []
	unchanged = []
	for row in rows:
		doc = frappe.get_doc(SMS_REGISTER_DOCTYPE, row.name)
		previous_status = doc.status
		doc.flags.ignore_permissions = True
		doc.save()

		result = {"name": doc.name, "status": doc.status}
		if doc.status != previous_status:
			updated.append(result)
		else:
			unchanged.append(result)

	return {
		"success": True,
		"checked": len(rows),
		"updated": updated,
		"unchanged": unchanged,
	}


@frappe.whitelist()
def get_sms_payments(company=None, pos_profile=None, search=None, amount=None, customer=None):
	search = (search or "").strip()
	amount = flt(amount or 0)
	if pos_profile and not company:
		company = frappe.db.get_value("POS Profile", pos_profile, "company")
	profile_mode = not get_global_sms_enabler_settings().get("sms_enabler_enabled")
	if profile_mode and not pos_profile:
		return {"count": 0, "payments": []}

	filters = {
		"status": ["in", ["Pending", "Matched", "Partially Allocated"]],
	}
	if company:
		filters["company"] = ["in", [company, "", None]]
	if profile_mode:
		filters["pos_profile"] = pos_profile

	payments = frappe.get_all(
		SMS_REGISTER_DOCTYPE,
		filters=filters,
		fields=[
			"name",
			"source",
			"sender",
			"transaction_id",
			"amount",
			"allocated_amount",
			"available_amount",
			"payer_name",
			"payer_phone",
			"account_reference",
			"received_at",
			"raw_message",
			"mode_of_payment",
			"company",
			"pos_profile",
			"sales_invoice",
			"payment_entry",
			"status",
		],
		order_by="received_at desc",
		limit_page_length=100,
	)

	search_lower = search.lower()
	customer_data = _get_customer_match_data(customer)
	matches = []
	for payment in payments:
		total_amount, allocated_amount, available_amount = _get_sms_payment_amounts(payment)
		if available_amount <= 0.01:
			continue
		payment["amount"] = total_amount
		payment["allocated_amount"] = allocated_amount
		payment["available_amount"] = available_amount
		payment["allocation_status"] = (
			_("Partially Allocated") if allocated_amount > 0 else _("Unallocated")
		)
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
	return {"count": len(matches), "payments": matches}


@frappe.whitelist()
def get_sms_payments_for_payment_reconciliation(
	company=None, party_type=None, party=None, search=None, pos_profile=None
):
	if party_type and party_type != "Customer":
		return {"count": 0, "payments": []}

	customer = party if party_type == "Customer" else None
	result = get_sms_payments(
		company=company,
		pos_profile=pos_profile,
		search=search,
		customer=customer,
	)
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
				"amount": flt(payment.get("available_amount")),
				"original_amount": flt(payment.get("amount")),
				"allocated_amount": flt(payment.get("allocated_amount")),
				"available_amount": flt(payment.get("available_amount")),
				"allocation_status": payment.get("allocation_status"),
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

	payment_allocations = _parse_payment_allocations(sms_payments)
	if not payment_allocations:
		frappe.throw(_("No SMS Enabler payments selected"))

	outstanding = flt(invoice_doc.outstanding_amount)
	if outstanding <= 0:
		frappe.throw(_("Invoice {0} is already fully paid").format(invoice))

	processed = []
	payment_entries_created = []
	for selected in payment_allocations:
		invoice_doc.reload()
		if flt(invoice_doc.outstanding_amount) <= 0.01:
			break

		name = selected["name"]
		payment = frappe.get_doc(SMS_REGISTER_DOCTYPE, name)
		if payment.status not in ("Pending", "Matched", "Partially Allocated"):
			frappe.throw(_("SMS payment {0} is already {1}").format(name, payment.status))
		if payment.company and payment.company != invoice_doc.company:
			frappe.throw(_("SMS payment {0} belongs to company {1}").format(name, payment.company))
		if payment.pos_profile and payment.pos_profile != invoice_doc.pos_profile:
			frappe.throw(
				_("SMS payment {0} belongs to POS Profile {1}").format(name, payment.pos_profile)
			)

		had_payment_entry = bool(payment.payment_entry)
		result = _apply_sms_payment_to_invoice(
			payment, invoice_doc, requested_amount=selected.get("amount")
		)
		processed.append(result)
		if not had_payment_entry:
			payment_entries_created.append(result["payment_entry"])

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
	payment_allocations = _parse_payment_allocations(sms_payments)
	if not payment_allocations:
		frappe.throw(_("No SMS Enabler payments selected"))

	selected_total = 0
	for item in payment_allocations:
		requested_amount = flt(item.get("amount"))
		if requested_amount <= 0:
			values = frappe.db.get_value(
				SMS_REGISTER_DOCTYPE,
				item["name"],
				["amount", "allocated_amount"],
				as_dict=True,
			) or {}
			requested_amount = max(
				flt(values.get("amount")) - flt(values.get("allocated_amount")),
				0,
			)
		selected_total += requested_amount

	# POS checkout normally includes SMS selections as direct Sales Invoice payment rows.
	# If the invoice still shows less paid than the selected SMS total, fall back to the
	# reconciliation path so the invoice is actually settled before the SMS rows are consumed.
	if (
		invoice_doc.docstatus == 1
		and selected_total > 0.01
		and flt(invoice_doc.outstanding_amount) > 0.01
	):
		return reconcile_invoice_with_sms_payments(
			invoice=invoice, sms_payments=payment_allocations
		)

	processed = []
	for selected in payment_allocations:
		name = selected["name"]
		payment = frappe.get_doc(SMS_REGISTER_DOCTYPE, name)
		if payment.status not in ("Pending", "Matched", "Partially Allocated"):
			frappe.throw(_("SMS payment {0} is already {1}").format(name, payment.status))
		if payment.pos_profile and payment.pos_profile != invoice_doc.pos_profile:
			frappe.throw(
				_("SMS payment {0} belongs to POS Profile {1}").format(name, payment.pos_profile)
			)

		total_amount, allocated_amount, available_amount = _get_sms_payment_amounts(payment)
		allocated_now = min(
			available_amount,
			flt(selected.get("amount")) or available_amount,
		)
		if allocated_now <= 0.01:
			continue

		mode_of_payment = payment.mode_of_payment or mode_of_payment
		new_allocated = min(allocated_amount + allocated_now, total_amount)
		new_available = max(total_amount - new_allocated, 0)
		payment_entry = payment.payment_entry or _find_payment_entry_for_sms(
			invoice,
			transaction_id=payment.transaction_id or payment.name,
			amount=allocated_now,
		)
		if new_available > 0.01 and not payment_entry:
			payment_entry = _create_sms_advance_payment_entry(
				payment,
				invoice_doc,
				new_available,
				mode_of_payment,
			)

		payment.customer = customer or invoice_doc.customer
		payment.company = company
		payment.pos_profile = payment.pos_profile or invoice_doc.pos_profile
		payment.sales_invoice = invoice
		payment.mode_of_payment = mode_of_payment
		payment.payment_entry = payment_entry
		payment.allocated_amount = new_allocated
		payment.available_amount = new_available
		payment.status = "Consumed" if new_available <= 0.01 else "Partially Allocated"
		payment.flags.ignore_permissions = True
		payment.save()

		processed.append(
			{
				"name": name,
				"original_amount": total_amount,
				"allocated_now": allocated_now,
				"allocated_amount": new_allocated,
				"available_amount": new_available,
				"mode_of_payment": payment.mode_of_payment,
				"sales_invoice": invoice,
				"payment_entry": payment.payment_entry,
				"status": payment.status,
			}
		)

	return {"success": True, "processed": processed}

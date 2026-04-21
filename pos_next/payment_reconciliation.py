# Copyright (c) 2025, BrainWise and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt


CHANGE_PAYMENT_TYPES = {"cash", "bank"}


def _read_payment_value(payment, key):
    if hasattr(payment, "get"):
        return payment.get(key)
    return getattr(payment, key, None)


def get_mode_of_payment_type(mode_of_payment):
    if not mode_of_payment:
        return ""

    return (
        frappe.db.get_value("Mode of Payment", mode_of_payment, "type") or ""
    ).strip().lower()


def payment_supports_change(payment, mode_types=None):
    payment_type = (_read_payment_value(payment, "type") or "").strip().lower()
    mode_of_payment = (_read_payment_value(payment, "mode_of_payment") or "").strip()
    mode_key = mode_of_payment.lower()

    if payment_type in CHANGE_PAYMENT_TYPES:
        return True

    if mode_key and any(token in mode_key for token in CHANGE_PAYMENT_TYPES):
        return True

    if not mode_of_payment:
        return False

    if mode_types is not None and mode_of_payment not in mode_types:
        mode_types[mode_of_payment] = get_mode_of_payment_type(mode_of_payment)

    return (mode_types or {}).get(mode_of_payment) in CHANGE_PAYMENT_TYPES


def resolve_change_mode_of_payment(payments):
    mode_types = {}

    for payment in reversed(list(payments or [])):
        if flt(_read_payment_value(payment, "amount")) <= 0:
            continue

        if payment_supports_change(payment, mode_types):
            return _read_payment_value(payment, "mode_of_payment")

    return None


def reconcile_change_against_payments(
    payments,
    outstanding_amount,
    explicit_change_amount=None,
):
    normalized_payments = []
    total_payment_amount = 0

    for payment in payments:
        payment_copy = dict(payment)
        payment_copy["amount"] = flt(payment_copy.get("amount", 0))
        normalized_payments.append(payment_copy)
        total_payment_amount += payment_copy["amount"]

    inferred_change_amount = max(flt(total_payment_amount - flt(outstanding_amount)), 0)
    requested_change_amount = max(flt(explicit_change_amount or 0), inferred_change_amount)
    remaining_change_amount = requested_change_amount
    mode_types = {}

    for payment in reversed(normalized_payments):
        if remaining_change_amount <= 0.01:
            break

        if payment.get("amount", 0) <= 0 or not payment_supports_change(payment, mode_types):
            continue

        change_applied = min(flt(payment.get("amount")), remaining_change_amount)
        payment["amount"] = flt(payment.get("amount") - change_applied)
        remaining_change_amount = flt(remaining_change_amount - change_applied)

    normalized_payments = [
        payment for payment in normalized_payments if flt(payment.get("amount")) > 0.01
    ]

    return normalized_payments, remaining_change_amount

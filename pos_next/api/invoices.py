# -*- coding: utf-8 -*-
# Copyright (c) 2025, BrainWise and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import json
from html import escape

import frappe
from frappe import _
from frappe.utils import (
    cint,
    cstr,
    flt,
    fmt_money,
    get_datetime,
    getdate,
    nowdate,
    nowtime,
)
from erpnext.stock.doctype.batch.batch import get_batch_qty, get_batch_no
from erpnext.accounts.doctype.sales_invoice.sales_invoice import get_bank_cash_account
from pos_next.pricing import resolve_profile_selling_price_list
from pos_next.payment_reconciliation import resolve_change_mode_of_payment

try:
    from erpnext.accounts.doctype.pricing_rule.pricing_rule import (
        apply_pricing_rule as erpnext_apply_pricing_rule,
    )
    from erpnext.accounts.doctype.pricing_rule.utils import (
        get_applied_pricing_rules as erpnext_get_applied_pricing_rules,
    )
except Exception:  # pragma: no cover - ERPNext not installed in some environments
    erpnext_apply_pricing_rule = None
    erpnext_get_applied_pricing_rules = None


# ==========================================
# Helper Functions
def normalize_sales_team_allocations(sales_team_data, invoice_total=0):
    """Validate POS sales team rows and normalize amount allocations to percentages."""
    if not sales_team_data:
        return []

    if isinstance(sales_team_data, str):
        sales_team_data = json.loads(sales_team_data or "[]")

    invoice_total = flt(invoice_total)
    normalized = []
    seen = set()

    for member in sales_team_data or []:
        sales_person = cstr(member.get("sales_person")).strip()
        if not sales_person:
            frappe.throw(_("Sales person is required."))

        if sales_person in seen:
            frappe.throw(_("Sales person {0} is selected more than once.").format(sales_person))
        seen.add(sales_person)

        if not frappe.db.exists("Sales Person", sales_person):
            frappe.throw(_("Sales Person {0} does not exist.").format(sales_person))

        allocated_percentage = flt(member.get("allocated_percentage"), 4)
        allocated_amount = flt(member.get("allocated_amount"), 2)

        if allocated_amount and not allocated_percentage:
            if not invoice_total:
                frappe.throw(_("Cannot allocate sales person amount because invoice total is zero."))
            allocated_percentage = flt((allocated_amount / invoice_total) * 100, 4)

        if allocated_percentage <= 0:
            frappe.throw(
                _("Sales person {0} must have an allocation greater than zero.").format(
                    sales_person
                )
            )

        normalized.append(
            {
                "sales_person": sales_person,
                "allocated_percentage": allocated_percentage,
            }
        )

    total_percentage = flt(
        sum(member["allocated_percentage"] for member in normalized), 4
    )
    difference = flt(100 - total_percentage, 4)

    if normalized and abs(difference) <= 0.05:
        normalized[-1]["allocated_percentage"] = flt(
            normalized[-1]["allocated_percentage"] + difference, 4
        )
        total_percentage = 100

    if normalized and abs(total_percentage - 100) > 0.05:
        frappe.throw(
            _("Sales person allocations must total 100%. Current total is {0}%.").format(
                total_percentage
            )
        )

    return normalized


def _is_item_sales_person_commission_enabled(pos_profile):
    if not pos_profile:
        return False

    try:
        if not frappe.get_meta("POS Settings").has_field("enable_item_sales_person_commission"):
            return False
        settings = frappe.db.get_value(
            "POS Settings",
            {"pos_profile": pos_profile, "enabled": 1},
            ["enable_item_sales_person_commission", "enable_sales_persons"],
            as_dict=True,
        )
        return bool(
            settings
            and cint(settings.get("enable_item_sales_person_commission"))
            and settings.get("enable_sales_persons") in ("Single", "Multiple")
        )
    except Exception:
        return False


def _get_invoice_item_commission_meta():
    meta = frappe.get_meta("Sales Invoice Item")
    return {
        "sales_person": meta.has_field("posa_sales_person"),
        "commission_rate": meta.has_field("posa_commission_rate"),
        "commission_amount": meta.has_field("posa_commission_amount"),
        "allocations": meta.has_field("posa_sales_person_allocations"),
    }


def _parse_item_sales_person_allocations(item):
    value = cstr(item.get("posa_sales_person_allocations")).strip()
    if not value:
        return []

    try:
        allocations = json.loads(value)
    except Exception:
        frappe.throw(
            _("Invalid sales person split for {0}.").format(item.get("item_name") or item.get("item_code")),
            title=_("Invalid Sales Person Split"),
        )

    if not isinstance(allocations, list):
        frappe.throw(
            _("Invalid sales person split for {0}.").format(item.get("item_name") or item.get("item_code")),
            title=_("Invalid Sales Person Split"),
        )

    return allocations


def _normalize_item_sales_person_allocations(item, fields):
    allocations = _parse_item_sales_person_allocations(item)
    if not allocations:
        return []

    item_label = item.get("item_name") or item.get("item_code")
    line_amount = flt(item.get("amount"), 2)
    item_commission_rate = flt(item.get("posa_commission_rate"), 4)
    total_percentage = flt(sum(flt(row.get("allocated_percentage"), 4) for row in allocations), 4)

    if not line_amount:
        return []
    if abs(total_percentage - 100) > 0.01:
        frappe.throw(
            _("Sales person split for {0} must total 100%. Currently {1}%.").format(
                item_label, total_percentage
            ),
            title=_("Invalid Sales Person Split"),
        )

    normalized = []
    allocated_amount = 0
    allocated_percentage = 0
    for index, row in enumerate(allocations):
        sales_person = cstr(row.get("sales_person")).strip()
        if not sales_person:
            frappe.throw(
                _("Select a sales person for every split row in {0}.").format(item_label),
                title=_("Sales Person Required"),
            )
        if not frappe.db.exists("Sales Person", sales_person):
            frappe.throw(_("Sales Person {0} does not exist.").format(sales_person))

        is_last = index == len(allocations) - 1
        percentage = flt(row.get("allocated_percentage"), 4)
        amount = flt(line_amount * percentage / 100, 2)
        if is_last:
            percentage = flt(100 - allocated_percentage, 4)
            amount = flt(line_amount - allocated_amount, 2)

        commission_rate = flt(row.get("commission_rate") if row.get("commission_rate") is not None else item_commission_rate, 4)
        if commission_rate < 0 or commission_rate > 100:
            frappe.throw(
                _("Commission rate for {0} must be between 0 and 100.").format(item_label)
            )

        normalized.append(
            {
                "sales_person": sales_person,
                "sales_person_name": cstr(row.get("sales_person_name")).strip() or sales_person,
                "allocated_percentage": percentage,
                "allocated_amount": amount,
                "commission_rate": commission_rate,
                "commission_amount": flt(amount * commission_rate / 100, 2),
            }
        )
        allocated_percentage = flt(allocated_percentage + percentage, 4)
        allocated_amount = flt(allocated_amount + amount, 2)

    if fields.get("allocations"):
        item.posa_sales_person_allocations = json.dumps(normalized, separators=(",", ":"))
    if fields.get("sales_person"):
        item.posa_sales_person = normalized[0]["sales_person"]
    if fields.get("commission_amount"):
        item.posa_commission_amount = flt(sum(row["commission_amount"] for row in normalized), 2)

    return normalized


def apply_item_sales_person_commissions(invoice_doc, require_sales_person=False):
    """Validate and calculate item-level sales person commission fields."""
    fields = _get_invoice_item_commission_meta()
    required_fields = [fields["sales_person"], fields["commission_rate"], fields["commission_amount"]]
    if require_sales_person and (not all(required_fields) or not fields.get("allocations")):
        frappe.throw(
            _("Item-level sales person commission fields are missing. Please run migrate for POS Next."),
            title=_("Missing Custom Fields"),
        )

    missing_items = []
    for item in invoice_doc.get("items", []):
        allocations = _normalize_item_sales_person_allocations(item, fields)
        sales_person = cstr(item.get("posa_sales_person")).strip()
        if require_sales_person and not allocations and not sales_person:
            missing_items.append(item.get("item_name") or item.get("item_code"))
            continue

        if sales_person and not frappe.db.exists("Sales Person", sales_person):
            frappe.throw(_("Sales Person {0} does not exist.").format(sales_person))

        commission_rate = flt(item.get("posa_commission_rate"), 4)
        if commission_rate < 0 or commission_rate > 100:
            frappe.throw(
                _("Commission rate for {0} must be between 0 and 100.").format(
                    item.get("item_name") or item.get("item_code")
                )
            )

        if fields["commission_amount"] and not allocations:
            item.posa_commission_amount = flt(flt(item.get("amount")) * commission_rate / 100, 2)

    if missing_items:
        frappe.throw(
            _("Select a sales person for: {0}").format(", ".join(missing_items)),
            title=_("Sales Person Required"),
        )


def build_sales_team_from_item_commissions(invoice_doc):
    """Build standard ERPNext Sales Team rows from item-level assignments."""
    totals = {}

    def add_amount(sales_person, amount):
        sales_person = cstr(sales_person).strip()
        if not sales_person:
            return
        totals[sales_person] = flt(totals.get(sales_person)) + flt(amount)

    for item in invoice_doc.get("items", []):
        allocations = _parse_item_sales_person_allocations(item)
        if allocations:
            for row in allocations:
                add_amount(row.get("sales_person"), row.get("allocated_amount"))
            continue
        add_amount(item.get("posa_sales_person"), item.get("amount"))

    total_amount = flt(sum(totals.values()))
    if not totals or total_amount <= 0:
        return []

    rows = []
    allocated = 0
    people = list(totals.items())
    for index, (sales_person, amount) in enumerate(people):
        if index == len(people) - 1:
            percentage = flt(100 - allocated, 4)
        else:
            percentage = flt((amount / total_amount) * 100, 4)
            allocated = flt(allocated + percentage, 4)
        rows.append(
            {
                "sales_person": sales_person,
                "allocated_percentage": percentage,
                "allocated_amount": amount,
            }
        )

    return rows


# ==========================================

CLIENT_TRANSACTION_FIELD = "posa_client_transaction_id"


def _invoice_submission_response(invoice_doc):
    return {
        "name": invoice_doc.name,
        "status": invoice_doc.docstatus,
        "grand_total": invoice_doc.grand_total,
        "total": invoice_doc.total,
        "net_total": invoice_doc.net_total,
        "outstanding_amount": invoice_doc.outstanding_amount,
        "paid_amount": invoice_doc.paid_amount,
        "change_amount": getattr(invoice_doc, "change_amount", 0),
    }


def _get_invoice_for_client_transaction(client_transaction_id, pos_profile=None):
    if not client_transaction_id:
        return None

    client_transaction_id = cstr(client_transaction_id).strip()
    if len(client_transaction_id) > 140:
        frappe.throw(_("Invalid checkout transaction ID"))

    existing = frappe.db.get_value(
        "Sales Invoice",
        {CLIENT_TRANSACTION_FIELD: client_transaction_id},
        ["name", "docstatus", "pos_profile"],
        as_dict=True,
    )
    if not existing:
        return None

    if pos_profile and existing.pos_profile != pos_profile:
        frappe.throw(_("Checkout transaction ID belongs to another POS Profile"))

    if existing.docstatus == 2:
        frappe.throw(
            _("The invoice for this checkout transaction was cancelled. Start a new sale.")
        )

    return frappe.get_doc("Sales Invoice", existing.name)


def get_payment_account(mode_of_payment, company):
    """
    Get account for mode of payment.
    Tries multiple fallback methods to find a suitable account.
    """
    # Try 1: Mode of Payment Account table
    account = frappe.db.get_value(
        "Mode of Payment Account",
        {"parent": mode_of_payment, "company": company},
        "default_account",
    )
    if account:
        return {"account": account}

    # Try 2: POS Payment Method from POS Profile
    try:
        columns = set(frappe.db.get_table_columns("POS Payment Method") or [])
    except Exception:
        columns = set()

    for account_field in ("default_account", "account", "payment_account"):
        if account_field not in columns:
            continue

        account = frappe.db.sql(
            f"""
			SELECT ppm.`{account_field}` as account
			FROM `tabPOS Payment Method` ppm
			INNER JOIN `tabPOS Profile` pp ON ppm.parent = pp.name
			WHERE ppm.mode_of_payment = %s
			AND pp.company = %s
			AND ppm.`{account_field}` IS NOT NULL
			LIMIT 1
		""",
            (mode_of_payment, company),
            as_dict=1,
        )

        if account and account[0].account:
            return {"account": account[0].account}

    # Try 3: Company default cash account (for cash payments)
    if "cash" in mode_of_payment.lower():
        account = frappe.get_value("Company", company, "default_cash_account")
        if account:
            return {"account": account}

    # Try 4: Company default bank account
    account = frappe.get_value("Company", company, "default_bank_account")
    if account:
        return {"account": account}

    # Try 5: Any Cash/Bank account for the company
    account = frappe.db.get_value(
        "Account",
        {"company": company, "account_type": ["in", ["Cash", "Bank"]], "is_group": 0},
        "name",
    )
    if account:
        return {"account": account}

    # No account found - throw error
    frappe.throw(
        _(
            "Please set default Cash or Bank account in Mode of Payment {0} or set default accounts in Company {1}"
        ).format(mode_of_payment, company),
        title=_("Missing Account"),
    )


def get_pos_change_account(pos_profile):
    if not pos_profile:
        return None

    try:
        profile_doc = frappe.get_cached_doc("POS Profile", pos_profile)
    except Exception:
        return None

    return (
        profile_doc.get("account_for_change_amount")
        or profile_doc.get("change_amount_account")
        or None
    )


def normalize_pos_invoice_payments(invoice_doc, company=None):
    """Make POS payment rows deterministic before saving/submitting.

    ERPNext derives paid/outstanding amounts from Sales Invoice Payment rows.
    POS Next builds those rows in the frontend, so we normalize the account and
    base amount server-side before ERPNext posts the invoice.
    """
    if not cint(invoice_doc.get("is_pos")):
        return

    company = company or invoice_doc.get("company")
    conversion_rate = flt(invoice_doc.get("conversion_rate") or 1) or 1
    total_paid = 0
    total_base_paid = 0

    for payment in invoice_doc.get("payments", []):
        amount = flt(payment.get("amount") or 0)
        if not amount and payment.get("base_amount"):
            amount = flt(payment.get("base_amount")) / conversion_rate

        payment.amount = amount
        payment.base_amount = flt(amount * conversion_rate)

        if payment.get("mode_of_payment") and company:
            account_info = get_payment_account(payment.mode_of_payment, company)
            payment.account = account_info.get("account")

        total_paid += amount
        total_base_paid += payment.base_amount

    invoice_doc.paid_amount = flt(total_paid)
    invoice_doc.base_paid_amount = flt(total_base_paid)

    grand_total = flt(invoice_doc.get("rounded_total") or invoice_doc.get("grand_total") or 0)
    base_grand_total = flt(
        invoice_doc.get("base_rounded_total")
        or invoice_doc.get("base_grand_total")
        or (grand_total * conversion_rate)
    )

    if not cint(invoice_doc.get("is_return")) and total_paid > grand_total:
        change_account = get_pos_change_account(invoice_doc.get("pos_profile"))
        change_mode_of_payment = resolve_change_mode_of_payment(invoice_doc.get("payments", []))

        if not change_mode_of_payment:
            frappe.throw(
                _(
                    "Change can only be reconciled against a Cash or Bank payment mode."
                )
            )

        if not change_account:
            frappe.throw(
                _(
                    "Set Account for Change Amount on POS Profile {0} before accepting overpayments."
                ).format(invoice_doc.get("pos_profile") or "")
            )

        invoice_doc.change_amount = flt(total_paid - grand_total)
        invoice_doc.base_change_amount = flt(total_base_paid - base_grand_total)
        if not invoice_doc.meta.has_field("account_for_change_amount"):
            frappe.throw(
                _(
                    "Sales Invoice is missing the Account for Change Amount field required for POS change reconciliation."
                )
            )
        invoice_doc.account_for_change_amount = change_account
        invoice_doc.outstanding_amount = 0
    else:
        invoice_doc.change_amount = 0
        invoice_doc.base_change_amount = 0
        if invoice_doc.meta.has_field("account_for_change_amount"):
            invoice_doc.account_for_change_amount = None
        invoice_doc.outstanding_amount = flt(grand_total - total_paid)


# ==========================================
# Stock Validation Functions
# ==========================================


def _get_available_stock(item):
    """Return available stock qty for an item row."""
    warehouse = item.get("warehouse")
    batch_no = item.get("batch_no")
    item_code = item.get("item_code")

    if not item_code or not warehouse:
        return 0

    if batch_no:
        return get_batch_qty(batch_no, warehouse) or 0

    # Get stock from Bin
    bin_qty = frappe.db.get_value(
        "Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty"
    )
    return flt(bin_qty) or 0


def _collect_stock_errors(items):
    """Return list of items exceeding available stock."""
    errors = []
    for d in items:
        if flt(d.get("qty")) < 0:
            continue

        available = _get_available_stock(d)
        requested = flt(
            d.get("stock_qty")
            or (flt(d.get("qty")) * flt(d.get("conversion_factor") or 1))
        )

        if requested > available:
            errors.append(
                {
                    "item_code": d.get("item_code"),
                    "warehouse": d.get("warehouse"),
                    "requested_qty": requested,
                    "available_qty": available,
                }
            )

    return errors


def _should_block(pos_profile):
    """Check if sale should be blocked for insufficient stock."""
    # First check global ERPNext Stock Settings
    allow_negative = cint(
        frappe.db.get_single_value("Stock Settings", "allow_negative_stock") or 0
    )
    if allow_negative:
        return False

    # Check POS Settings for the specific profile
    if pos_profile:
        # Check if POS Settings allows negative stock
        pos_settings_allow_negative = cint(
            frappe.db.get_value(
                "POS Settings",
                {"pos_profile": pos_profile},
                "allow_negative_stock"
            ) or 0
        )
        if pos_settings_allow_negative:
            return False

        # Try to get custom field (may not exist in vanilla ERPNext)
        block_sale = cint(
            frappe.db.get_value(
                "POS Profile", pos_profile, "posa_block_sale_beyond_available_qty"
            )
            or 1
        )
        return bool(block_sale)

    # Default to blocking if no profile specified
    return True


def _should_block_zero_price_sales(pos_profile):
    """Return true when POS Settings disallows zero or missing item prices."""
    if not pos_profile:
        return False

    return bool(
        cint(
            frappe.db.get_value(
                "POS Settings",
                {"pos_profile": pos_profile, "enabled": 1},
                "block_zero_price_sales",
            )
            or 0
        )
    )


def _collect_zero_price_errors(items):
    """Return invoice items whose selling price is zero or missing."""
    errors = []
    for item in items or []:
        qty = flt(item.get("qty") or item.get("quantity") or 0)
        if qty < 0:
            continue

        selling_price = flt(item.get("price_list_rate") or item.get("rate") or 0)
        if selling_price <= 0:
            errors.append(
                {
                    "item_code": item.get("item_code"),
                    "item_name": item.get("item_name"),
                }
            )

    return errors


def _validate_zero_price_items(invoice_doc):
    """Block invoices containing items with no configured selling price."""
    if not _should_block_zero_price_sales(invoice_doc.get("pos_profile")):
        return

    errors = _collect_zero_price_errors(
        [d.as_dict() for d in invoice_doc.get("items", [])]
    )
    if not errors:
        return

    item_labels = [
        error.get("item_name") or error.get("item_code")
        for error in errors
        if error.get("item_name") or error.get("item_code")
    ]
    frappe.throw(
        _("Selling price is 0.00 or has not been set for: {0}").format(
            ", ".join(item_labels)
        ),
        title=_("Zero Selling Price Blocked"),
    )


def _validate_stock_on_invoice(invoice_doc):
    """Validate stock availability before submission."""
    if invoice_doc.doctype == "Sales Invoice" and not cint(
        getattr(invoice_doc, "update_stock", 0)
    ):
        return

    # Collect all stock items to check
    items_to_check = [d.as_dict() for d in invoice_doc.items if d.get("is_stock_item")]

    # Include packed items if present
    if hasattr(invoice_doc, "packed_items"):
        items_to_check.extend([d.as_dict() for d in invoice_doc.packed_items])

    # Check for stock errors
    errors = _collect_stock_errors(items_to_check)

    # Throw error if stock insufficient and blocking is enabled
    if errors and _should_block(invoice_doc.pos_profile):
        frappe.throw(frappe.as_json({"errors": errors}), frappe.ValidationError)


def _auto_set_return_batches(invoice_doc):
    """Assign batch numbers for return invoices without a source invoice.

    When an item requires a batch number, this function allocates the first
    available batch in FIFO order. If no batches exist in the selected
    warehouse, an informative error is raised.
    """
    if not invoice_doc.is_return or invoice_doc.get("return_against"):
        return

    for d in invoice_doc.items:
        if not d.get("item_code") or not d.get("warehouse"):
            continue

        has_batch = frappe.db.get_value("Item", d.item_code, "has_batch_no")
        if has_batch and not d.get("batch_no"):
            batch_list = (
                get_batch_qty(item_code=d.item_code, warehouse=d.warehouse) or []
            )
            batch_list = [b for b in batch_list if flt(b.get("qty")) > 0]

            if batch_list:
                # FIFO: batches are already sorted by posting/expiry in ERPNext
                d.batch_no = batch_list[0].get("batch_no")
            else:
                frappe.throw(
                    _("No batches available in {0} for {1}.").format(
                        d.warehouse, d.item_code
                    )
                )


# ==========================================
# Validation Functions
# ==========================================


@frappe.whitelist()
def validate_cart_items(items, pos_profile=None):
    """Validate cart items for available stock.

    Returns a list of item dicts where requested quantity exceeds availability.
    This can be used on the front-end for pre-submission checks.
    """
    if isinstance(items, str):
        items = json.loads(items)

    if pos_profile and not frappe.db.exists("POS Profile", pos_profile):
        pos_profile = None

    if not _should_block(pos_profile):
        return []

    errors = _collect_stock_errors(items)
    if not errors:
        return []

    return errors


@frappe.whitelist()
def validate_return_items(original_invoice_name, return_items, doctype="Sales Invoice"):
    """Ensure that return items do not exceed the quantity from the original invoice."""
    original_invoice = frappe.get_doc(doctype, original_invoice_name)
    original_item_qty = {}

    for item in original_invoice.items:
        original_item_qty[item.item_code] = (
            original_item_qty.get(item.item_code, 0) + item.qty
        )

    # Get all returned items from this invoice
    returned_items = frappe.get_all(
        doctype,
        filters={
            "return_against": original_invoice_name,
            "docstatus": 1,
            "is_return": 1,
        },
        fields=["name"],
    )

    for returned_invoice in returned_items:
        ret_doc = frappe.get_doc(doctype, returned_invoice.name)
        for item in ret_doc.items:
            if item.item_code in original_item_qty:
                original_item_qty[item.item_code] -= abs(item.qty)

    # Validate new return items
    for item in return_items:
        item_code = item.get("item_code")
        return_qty = abs(item.get("qty", 0))
        if item_code in original_item_qty and return_qty > original_item_qty[item_code]:
            return {
                "valid": False,
                "message": _(
                    "You are trying to return more quantity for item {0} than was sold."
                ).format(item_code),
            }

    return {"valid": True}


# ==========================================
# Invoice Management (Two-Step Flow)
# ==========================================


@frappe.whitelist()
def update_invoice(data):
    """Create or update invoice draft (Step 1)."""
    try:
        data = json.loads(data) if isinstance(data, str) else data

        pos_profile = data.get("pos_profile")
        doctype = "Sales Invoice"

        # Ensure the document type is set
        data.setdefault("doctype", doctype)

        # Create or update invoice
        if data.get("name") and frappe.db.exists(doctype, data.get("name")):
            invoice_doc = frappe.get_doc(doctype, data.get("name"))
            invoice_doc.update(data)
        else:
            invoice_doc = frappe.get_doc(data)

        pos_profile_doc = None
        if pos_profile:
            try:
                pos_profile_doc = frappe.get_cached_doc("POS Profile", pos_profile)
            except Exception as profile_err:
                frappe.throw(_("Unable to load POS Profile {0}").format(pos_profile))

            invoice_doc.pos_profile = pos_profile

            if pos_profile_doc.company and not invoice_doc.get("company"):
                invoice_doc.company = pos_profile_doc.company
            if pos_profile_doc.currency and not invoice_doc.get("currency"):
                invoice_doc.currency = pos_profile_doc.currency

            effective_price_list = (
                invoice_doc.get("selling_price_list")
                or data.get("price_list")
                or resolve_profile_selling_price_list(
                    pos_profile_doc,
                    customer=invoice_doc.get("customer"),
                    customer_group=invoice_doc.get("customer_group"),
                    warehouse=(
                        invoice_doc.get("items", [{}])[0].get("warehouse")
                        if invoice_doc.get("items")
                        else pos_profile_doc.warehouse
                    ),
                )
            )
            if effective_price_list:
                invoice_doc.selling_price_list = effective_price_list

            # Copy accounting dimensions from POS Profile
            if hasattr(pos_profile_doc, "branch") and pos_profile_doc.branch:
                invoice_doc.branch = pos_profile_doc.branch
                # Also set branch on all items for GL entries
                for item in invoice_doc.get("items", []):
                    item.branch = pos_profile_doc.branch

        company = invoice_doc.get("company") or (
            pos_profile_doc.company if pos_profile_doc else None
        )

        if company and invoice_doc.get("payments"):
            for payment in invoice_doc.payments:
                if payment.mode_of_payment and not payment.get("account"):
                    try:
                        account_info = get_payment_account(
                            payment.mode_of_payment, company
                        )
                        payment.account = account_info.get("account")
                    except Exception:
                        pass  # Will be handled during save

        # Validate return items if this is a return invoice
        if (data.get("is_return") or invoice_doc.is_return) and invoice_doc.get(
            "return_against"
        ):
            validation = validate_return_items(
                invoice_doc.return_against,
                [d.as_dict() for d in invoice_doc.items],
                doctype=invoice_doc.doctype,
            )
            if not validation.get("valid"):
                frappe.throw(validation.get("message"))

        # Ensure customer exists
        customer_name = invoice_doc.get("customer")
        if customer_name and not frappe.db.exists("Customer", customer_name):
            try:
                cust = frappe.get_doc(
                    {
                        "doctype": "Customer",
                        "customer_name": customer_name,
                        "customer_group": "All Customer Groups",
                        "territory": "All Territories",
                        "customer_type": "Individual",
                    }
                )
                cust.flags.ignore_permissions = True
                cust.insert()
                invoice_doc.customer = cust.name
                invoice_doc.customer_name = cust.customer_name
            except Exception as e:
                frappe.log_error(f"Failed to create customer {customer_name}: {e}")

        # Disable automatic pricing rules (we handle discounts manually from POS)
        invoice_doc.ignore_pricing_rule = 1
        invoice_doc.flags.ignore_pricing_rule = True

        # ========================================================================
        # DISCOUNT CALCULATION - CRITICAL LOGIC
        # ========================================================================
        # Problem: Frontend sends rate (discounted) and discount_percentage
        # Solution: Reverse-calculate price_list_rate (original price) to avoid double discount
        #
        # Formula: rate = price_list_rate * (1 - discount_percentage/100)
        # Reverse: price_list_rate = rate / (1 - discount_percentage/100)
        # ========================================================================
        for item in invoice_doc.get("items", []):
            item_rate = flt(item.rate or 0)
            discount_pct = flt(item.discount_percentage or 0)

            # If item has a discount, reverse-calculate the original price_list_rate
            if discount_pct > 0 and discount_pct < 100:
                if item_rate > 0:
                    # Reverse calculation to get original price
                    item.price_list_rate = item_rate / (1 - discount_pct / 100)
                elif not item.get("price_list_rate"):
                    # Fallback: if rate is 0 but discount exists (edge case)
                    item.price_list_rate = item_rate
            elif not item.get("price_list_rate"):
                # No discount or price_list_rate not set - use rate as is
                item.price_list_rate = item_rate

            # Ensure price_list_rate is never less than rate (data integrity)
            if flt(item.price_list_rate) < item_rate:
                item.price_list_rate = item_rate

            # IMPORTANT: Keep the rate from frontend (do NOT set to 0)
            # ERPNext will recalculate if needed, but preserving frontend rate
            # prevents rounding issues and ensures UI matches invoice

        _validate_zero_price_items(invoice_doc)

        # Set invoice flags BEFORE calculations
        invoice_doc.is_pos = 1
        invoice_doc.update_stock = 1

        # ========================================================================
        # ROUNDING CONFIGURATION
        # ========================================================================
        # Load rounding preference from POS Settings
        # When disabled (0): ERPNext rounds to nearest whole number
        # When enabled (1): Shows exact amount without rounding
        # ========================================================================
        disable_rounded = 1  # Default: disable rounding for POS (show exact amounts)

        if pos_profile:
            try:
                pos_settings_value = frappe.db.get_value(
                    "POS Settings",
                    {"pos_profile": pos_profile},
                    "disable_rounded_total"
                )
                if pos_settings_value is not None:
                    disable_rounded = cint(pos_settings_value)
            except Exception as e:
                # Log error but continue with default
                frappe.log_error(f"Error loading rounding setting: {str(e)}", "POS Invoice Creation")

        invoice_doc.disable_rounded_total = disable_rounded

        incoming_payments = [
            {
                "mode_of_payment": payment.get("mode_of_payment"),
                "amount": flt(payment.get("amount")),
                "type": payment.get("type"),
                "account": payment.get("account"),
                "base_amount": flt(payment.get("base_amount")),
            }
            for payment in invoice_doc.get("payments", [])
            if payment.get("mode_of_payment") and flt(payment.get("amount") or payment.get("base_amount")) > 0
        ]

        # Populate missing fields (company, currency, accounts, etc.)
        invoice_doc.set_missing_values()

        # Calculate totals and apply discounts (with rounding disabled)
        invoice_doc.calculate_taxes_and_totals()

        if incoming_payments:
            invoice_doc.set("payments", [])
            for payment in incoming_payments:
                invoice_doc.append("payments", payment)

        normalize_pos_invoice_payments(invoice_doc, invoice_doc.company)
        apply_item_sales_person_commissions(invoice_doc)

        # For return invoices, ensure payments are negative
        if invoice_doc.is_return:
            for payment in invoice_doc.payments:
                payment.amount = -abs(payment.amount)
                if payment.base_amount:
                    payment.base_amount = -abs(payment.base_amount)

            invoice_doc.paid_amount = flt(sum(p.amount for p in invoice_doc.payments))
            invoice_doc.base_paid_amount = flt(
                sum(p.base_amount or 0 for p in invoice_doc.payments)
            )
            grand_total = flt(
                invoice_doc.get("rounded_total") or invoice_doc.get("grand_total") or 0
            )
            invoice_doc.outstanding_amount = flt(grand_total - invoice_doc.paid_amount)
            invoice_doc.change_amount = 0
            invoice_doc.base_change_amount = 0
            if invoice_doc.meta.has_field("account_for_change_amount"):
                invoice_doc.account_for_change_amount = None

        # Validate and track POS Coupon if coupon_code is provided
        coupon_code = data.get("coupon_code")
        if coupon_code:
            # Validate POS Coupon exists and is valid
            if frappe.db.table_exists("POS Coupon"):
                from pos_next.pos_next.doctype.pos_coupon.pos_coupon import check_coupon_code

                coupon_result = check_coupon_code(
                    coupon_code,
                    customer=invoice_doc.customer,
                    company=invoice_doc.company
                )

                if not coupon_result.get("valid"):
                    frappe.throw(_(coupon_result.get("msg", "Invalid coupon code")))

                # Store coupon code on invoice for tracking
                invoice_doc.coupon_code = coupon_code

        # Save as draft
        invoice_doc.flags.ignore_permissions = True
        frappe.flags.ignore_account_permission = True
        invoice_doc.docstatus = 0
        invoice_doc.save()

        return invoice_doc.as_dict()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Invoice Error")
        raise


@frappe.whitelist()
def submit_invoice(invoice=None, data=None):
    """Submit the invoice (Step 2)."""
    try:

        # Handle different calling conventions
        if invoice is None:
            if data:
                # Check if data is a JSON string containing both params
                data_parsed = json.loads(data) if isinstance(data, str) else data

                # frappe-ui might send all params nested in data
                if isinstance(data_parsed, dict):
                    if "invoice" in data_parsed:
                        invoice = data_parsed.get("invoice")
                        data = data_parsed.get("data", {})
                    elif "name" in data_parsed or "doctype" in data_parsed:
                        # Data itself might be the invoice
                        invoice = data_parsed
                        data = {}
                    else:
                        frappe.throw(
                            _("Missing invoice parameter. Received data: {0}").format(
                                json.dumps(data_parsed, default=str)
                            )
                        )
                else:
                    frappe.throw(_("Missing invoice parameter"))
            else:
                frappe.throw(_("Both invoice and data parameters are missing"))

        # Parse JSON strings if needed
        if isinstance(data, str):
            data = json.loads(data) if data and data != "{}" else {}
        if isinstance(invoice, str):
            invoice = json.loads(invoice)

        pos_profile = invoice.get("pos_profile")
        doctype = "Sales Invoice"
        is_credit_sale = cint((data or {}).get("is_credit_sale") or invoice.get("is_credit_sale"))
        client_transaction_id = cstr(
            invoice.get(CLIENT_TRANSACTION_FIELD)
            or (data or {}).get("client_transaction_id")
        ).strip()

        if client_transaction_id:
            invoice[CLIENT_TRANSACTION_FIELD] = client_transaction_id
            existing_transaction_invoice = _get_invoice_for_client_transaction(
                client_transaction_id,
                pos_profile,
            )
            if existing_transaction_invoice:
                if existing_transaction_invoice.docstatus == 1:
                    return _invoice_submission_response(existing_transaction_invoice)
                invoice["name"] = existing_transaction_invoice.name

        if is_credit_sale:
            from pos_next.pos_next.doctype.pos_settings.pos_settings import (
                is_credit_sale_allowed_for_user,
            )

            if not is_credit_sale_allowed_for_user(pos_profile):
                frappe.throw(_("You are not allowed to create credit sales for this POS Profile"))

        invoice_name = invoice.get("name")

        # Get or create invoice
        if not invoice_name or not frappe.db.exists(doctype, invoice_name):
            created = update_invoice(json.dumps(invoice))
            invoice_name = created.get("name")
            invoice_doc = frappe.get_doc(doctype, invoice_name)
        else:
            invoice_doc = frappe.get_doc(doctype, invoice_name)
            invoice_doc.update(invoice)

        # Ensure update_stock is set
        invoice_doc.update_stock = 1

        # Copy accounting dimensions from POS Profile if not already set
        if pos_profile and not invoice_doc.get("branch"):
            try:
                pos_profile_doc = frappe.get_cached_doc("POS Profile", pos_profile)
                if hasattr(pos_profile_doc, "branch") and pos_profile_doc.branch:
                    invoice_doc.branch = pos_profile_doc.branch
                    # Also set branch on all items for GL entries
                    for item in invoice_doc.get("items", []):
                        if not item.get("branch"):
                            item.branch = pos_profile_doc.branch
            except Exception:
                pass  # Branch is optional, continue without it

        normalize_pos_invoice_payments(invoice_doc, invoice_doc.company)

        item_sales_person_commission_enabled = _is_item_sales_person_commission_enabled(pos_profile)
        apply_item_sales_person_commissions(
            invoice_doc,
            require_sales_person=item_sales_person_commission_enabled,
        )

        # Handle sales team (single or multiple sales persons)
        sales_team_data = (
            build_sales_team_from_item_commissions(invoice_doc)
            if item_sales_person_commission_enabled
            else invoice.get("sales_team") or data.get("sales_team")
        )
        normalized_sales_team = normalize_sales_team_allocations(
            sales_team_data,
            invoice_doc.get("rounded_total") or invoice_doc.get("grand_total") or 0,
        )
        if normalized_sales_team:
            invoice_doc.sales_team = []
            for member in normalized_sales_team:
                invoice_doc.append(
                    "sales_team",
                    {
                        "sales_person": member.get("sales_person"),
                        "allocated_percentage": member.get("allocated_percentage"),
                    },
                )

        # Handle POS Coupon if coupon_code is provided
        coupon_code = invoice.get("coupon_code") or data.get("coupon_code")
        if coupon_code:
            # Increment usage counter for POS Coupon
            if frappe.db.table_exists("POS Coupon"):
                try:
                    from pos_next.pos_next.doctype.pos_coupon.pos_coupon import increment_coupon_usage
                    increment_coupon_usage(coupon_code)
                except Exception as e:
                    frappe.log_error(
                        title="Failed to increment coupon usage",
                        message=f"Coupon: {coupon_code}, Error: {str(e)}"
                    )

        # Auto-set batch numbers for returns
        _auto_set_return_batches(invoice_doc)

        # Check if POS Settings allows negative stock
        pos_settings_allow_negative = False
        if pos_profile:
            pos_settings_allow_negative = cint(
                frappe.db.get_value(
                    "POS Settings",
                    {"pos_profile": pos_profile},
                    "allow_negative_stock"
                ) or 0
            )

        # Validate stock availability only if negative stock is not allowed
        if not pos_settings_allow_negative:
            _validate_stock_on_invoice(invoice_doc)

        _validate_zero_price_items(invoice_doc)

        # Save before submit
        invoice_doc.flags.ignore_permissions = True
        frappe.flags.ignore_account_permission = True
        invoice_doc.save()

        # Submit invoice with error handling
        # Note: Negative stock handling is now done through the CustomSalesInvoice override
        # which checks POS Settings in the update_stock_ledger method
        try:
            invoice_doc.submit()
            try:
                from pos_next.pos_next.doctype.cash_payment_register.cash_payment_register import (
                    register_inline_pos_cash_payments,
                )

                register_inline_pos_cash_payments(invoice_doc)
            except Exception:
                frappe.log_error(
                    title=f"Failed to register inline cash payments for {invoice_doc.name}",
                    message=frappe.get_traceback(),
                )
        except Exception as submit_error:
            # If submission fails, cleanup the invoice to prevent stock reservation issues
            try:
                # Reload to get current state
                current_doc = frappe.get_doc("Sales Invoice", invoice_doc.name)

                # If already submitted, must cancel before deleting
                if current_doc.docstatus == 1:
                    current_doc.flags.ignore_permissions = True
                    current_doc.cancel()

                # Now delete the cancelled/draft invoice
                frappe.delete_doc(
                    "Sales Invoice",
                    invoice_doc.name,
                    force=True,
                    ignore_permissions=True,
                )
                frappe.db.commit()
            except Exception:
                # Silent fail on cleanup - don't hide original error
                pass

            # Re-raise the original submission error
            raise submit_error

        # Handle credit redemption after successful submission
        customer_credit_dict = data.get("customer_credit_dict") or invoice.get("customer_credit_dict")
        redeemed_customer_credit = data.get("redeemed_customer_credit") or invoice.get("redeemed_customer_credit")

        if redeemed_customer_credit and customer_credit_dict:
            try:
                from pos_next.api.credit_sales import redeem_customer_credit
                redeem_customer_credit(invoice_doc.name, customer_credit_dict)
            except Exception as credit_error:
                frappe.log_error(
                    title="Credit Redemption Error",
                    message=f"Invoice: {invoice_doc.name}, Error: {str(credit_error)}\n{frappe.get_traceback()}"
                )
                # Don't fail the entire transaction, just log the error
                frappe.msgprint(
                    _("Invoice submitted successfully but credit redemption failed. Please contact administrator."),
                    alert=True,
                    indicator="orange"
                )

        # Return complete invoice details
        return _invoice_submission_response(invoice_doc)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Submit Invoice Error")
        raise


# ==========================================
# Invoice History Management
# ==========================================


@frappe.whitelist()
def get_invoice(invoice_name):
	"""
	Get a single invoice with all details for POS.

	Args:
		invoice_name: Sales Invoice name

	Returns:
		Complete invoice document with items and payments
	"""
	if not invoice_name:
		frappe.throw(_("Invoice name is required"))

	if not frappe.db.exists("Sales Invoice", invoice_name):
		frappe.throw(_("Invoice {0} does not exist").format(invoice_name))

	# Check permissions
	if not frappe.has_permission("Sales Invoice", "read", invoice_name):
		frappe.throw(_("You don't have permission to view this invoice"))

	# Get invoice document
	invoice = frappe.get_doc("Sales Invoice", invoice_name)

	invoice_data = invoice.as_dict()

	try:
		from pos_next.api.partial_payments import get_payment_history

		payment_data = get_payment_history(invoice_name, include_metadata=True)
		invoice_data.paid_amount = payment_data.get("total_paid")
		invoice_data.outstanding_amount = payment_data.get("outstanding")
		if payment_data.get("payments"):
			invoice_data.payments = payment_data.get("payments")
	except Exception:
		frappe.log_error(
			title=f"Failed to enrich invoice payment history for {invoice_name}",
			message=frappe.get_traceback(),
		)

	return invoice_data


@frappe.whitelist()
def diagnose_invoice_payments(invoice_name):
	"""Inspect the stored payment rows Sales Register filters against."""
	if not invoice_name:
		frappe.throw(_("Invoice name is required"))

	if not frappe.db.exists("Sales Invoice", invoice_name):
		frappe.throw(_("Invoice {0} does not exist").format(invoice_name))

	invoice = frappe.db.get_value(
		"Sales Invoice",
		invoice_name,
		[
			"name",
			"docstatus",
			"is_pos",
			"posting_date",
			"company",
			"customer",
			"grand_total",
			"paid_amount",
			"outstanding_amount",
			"status",
		],
		as_dict=True,
	)
	sales_invoice_payments = frappe.get_all(
		"Sales Invoice Payment",
		filters={"parent": invoice_name},
		fields=["name", "parent", "mode_of_payment", "amount", "base_amount", "account", "idx"],
		order_by="idx asc",
	)
	payment_entries = frappe.db.sql(
		"""
		SELECT
			pe.name,
			pe.docstatus,
			pe.mode_of_payment,
			pe.paid_amount,
			pe.received_amount,
			pe.reference_no,
			per.allocated_amount
		FROM `tabPayment Entry` pe
		INNER JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
		WHERE per.reference_doctype = 'Sales Invoice'
			AND per.reference_name = %(invoice_name)s
		ORDER BY pe.creation ASC
		""",
		{"invoice_name": invoice_name},
		as_dict=True,
	)

	return {
		"invoice": invoice,
		"sales_invoice_payments": sales_invoice_payments,
		"payment_entries": payment_entries,
		"sales_register_modes": sorted(
			{
				payment.mode_of_payment
				for payment in sales_invoice_payments
				if payment.mode_of_payment
			}
		),
	}


@frappe.whitelist()
def get_invoices(pos_profile, limit=100):
	"""
	Get list of invoices for a POS Profile.

	Args:
		pos_profile: POS Profile name
		limit: Maximum number of invoices to return (default 100)

	Returns:
		List of invoices with details
	"""
	if not pos_profile:
		frappe.throw(_("POS Profile is required"))

	# Check if user has access to this POS Profile
	has_access = frappe.db.exists(
		"POS Profile User",
		{"parent": pos_profile, "user": frappe.session.user}
	)

	if not has_access and not frappe.has_permission("Sales Invoice", "read"):
		frappe.throw(_("You don't have access to this POS Profile"))

	# Query for invoices
	invoices = frappe.db.sql("""
		SELECT
			name,
			customer,
			customer_name,
			posting_date,
			posting_time,
			grand_total,
			paid_amount,
			outstanding_amount,
			status,
			docstatus,
			is_return,
			return_against
		FROM
			`tabSales Invoice`
		WHERE
			pos_profile = %(pos_profile)s
			AND docstatus = 1
			AND is_pos = 1
		ORDER BY
			posting_date DESC,
			posting_time DESC
		LIMIT %(limit)s
	""", {
		"pos_profile": pos_profile,
		"limit": limit
	}, as_dict=True)

	try:
		from pos_next.api.partial_payments import enrich_invoice_with_payment_history
	except Exception:
		enrich_invoice_with_payment_history = None

	# Load items for each invoice for filtering purposes
	for invoice in invoices:
		items = frappe.db.sql("""
			SELECT
				item_code,
				item_name,
				qty,
				rate,
				amount
			FROM
				`tabSales Invoice Item`
			WHERE
				parent = %(invoice_name)s
			ORDER BY
				idx
		""", {
			"invoice_name": invoice.name
		}, as_dict=True)
		invoice.items = items

		if not enrich_invoice_with_payment_history:
			continue

		try:
			enrich_invoice_with_payment_history(invoice, include_metadata=True)
		except Exception:
			frappe.log_error(
				title=f"Failed to enrich invoice payment history for {invoice.name}",
				message=frappe.get_traceback(),
			)

	return invoices

def can_view_cash_report_figures():
	"""Only managers should see cash and payment collection figures in POS reports."""
	roles = set(frappe.get_roles(frappe.session.user) or [])
	return bool(roles.intersection({"Sales Manager", "System Manager"}))



def _validate_sales_report_access(pos_profile, from_date=None, to_date=None):
	if not pos_profile:
		frappe.throw(_("POS Profile is required"))

	has_access = frappe.db.exists(
		"POS Profile User",
		{"parent": pos_profile, "user": frappe.session.user},
	)
	if not has_access and not frappe.has_permission("Sales Invoice", "read"):
		frappe.throw(_("You don't have access to this POS Profile"))

	from_date = getdate(from_date or nowdate())
	to_date = getdate(to_date or nowdate())
	if from_date > to_date:
		frappe.throw(_("From Date cannot be after To Date"))

	return from_date, to_date


def _get_sales_report_payment_export(
	pos_profile,
	from_date,
	to_date,
	sales_person=None,
):
	params = {
		"pos_profile": pos_profile,
		"from_date": from_date,
		"to_date": to_date,
		"sales_person": cstr(sales_person).strip(),
	}
	sales_person_filter = """
		AND (
			%(sales_person)s = ''
			OR EXISTS (
				SELECT 1
				FROM `tabSales Team` sales_team_filter
				WHERE sales_team_filter.parent = si.name
					AND sales_team_filter.parenttype = 'Sales Invoice'
					AND sales_team_filter.sales_person = %(sales_person)s
			)
		)
	"""
	invoices = frappe.db.sql(
		f"""
		SELECT
			si.name,
			si.posting_date,
			si.posting_time,
			si.paid_amount,
			si.outstanding_amount,
			si.grand_total,
			si.is_return,
			(
				SELECT GROUP_CONCAT(
					DISTINCT sales_team.sales_person
					ORDER BY sales_team.sales_person
					SEPARATOR ', '
				)
				FROM `tabSales Team` sales_team
				WHERE sales_team.parent = si.name
					AND sales_team.parenttype = 'Sales Invoice'
			) AS sales_person
		FROM `tabSales Invoice` si
		WHERE si.pos_profile = %(pos_profile)s
			AND si.docstatus = 1
			AND si.is_pos = 1
			AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
			{sales_person_filter}
		ORDER BY si.posting_date ASC, si.posting_time ASC, si.name ASC
		""",
		params,
		as_dict=True,
	)

	inline_payments = frappe.db.sql(
		f"""
		SELECT
			si.name AS invoice_id,
			sip.mode_of_payment,
			COALESCE(
				SUM(
					CASE
						WHEN si.is_return = 1 THEN -ABS(sip.amount)
						ELSE sip.amount
					END
				),
				0
			) AS amount
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Payment` sip ON sip.parent = si.name
		WHERE si.pos_profile = %(pos_profile)s
			AND si.docstatus = 1
			AND si.is_pos = 1
			AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND sip.amount != 0
			{sales_person_filter}
		GROUP BY si.name, sip.mode_of_payment
		""",
		params,
		as_dict=True,
	)

	payment_entries = frappe.db.sql(
		f"""
		SELECT
			si.name AS invoice_id,
			pe.mode_of_payment,
			COALESCE(
				SUM(
					CASE
						WHEN si.is_return = 1 THEN -ABS(per.allocated_amount)
						ELSE per.allocated_amount
					END
				),
				0
			) AS amount
		FROM `tabSales Invoice` si
		INNER JOIN `tabPayment Entry Reference` per
			ON per.reference_doctype = 'Sales Invoice'
			AND per.reference_name = si.name
		INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
		WHERE si.pos_profile = %(pos_profile)s
			AND si.docstatus = 1
			AND si.is_pos = 1
			AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND pe.docstatus = 1
			AND per.allocated_amount != 0
			{sales_person_filter}
		GROUP BY si.name, pe.mode_of_payment
		""",
		params,
		as_dict=True,
	)

	payments_by_invoice = {}
	for payment in list(inline_payments or []) + list(payment_entries or []):
		invoice_id = payment.get("invoice_id")
		mode_of_payment = payment.get("mode_of_payment") or _("Unspecified")
		invoice_payments = payments_by_invoice.setdefault(invoice_id, {})
		invoice_payments[mode_of_payment] = (
			flt(invoice_payments.get(mode_of_payment)) + flt(payment.get("amount"))
		)

	rows = []
	mode_totals = {}
	for invoice in invoices:
		invoice_payments = dict(payments_by_invoice.get(invoice.name) or {})
		allocated_amount = flt(sum(invoice_payments.values()))
		unallocated_amount = flt(invoice.grand_total) - allocated_amount
		if abs(unallocated_amount) > 0.005:
			mode = (
				_("Unpaid / Credit")
				if abs(flt(invoice.outstanding_amount)) > 0.005
				else _("Unspecified")
			)
			invoice_payments[mode] = (
				flt(invoice_payments.get(mode)) + unallocated_amount
			)
		elif not invoice_payments:
			invoice_payments[_("Unspecified")] = 0

		for mode_of_payment, amount in sorted(invoice_payments.items()):
			rows.append(
				{
					"posting_date": invoice.posting_date,
					"invoice_id": invoice.name,
					"sales_person": invoice.sales_person or _("Unassigned"),
					"mode_of_payment": mode_of_payment,
					"amount": flt(amount),
				}
			)
			mode_totals[mode_of_payment] = (
				flt(mode_totals.get(mode_of_payment)) + flt(amount)
			)

	return {
		"rows": rows,
		"sales_person": cstr(sales_person).strip(),
		"mode_totals": [
			{"mode_of_payment": mode, "amount": amount}
			for mode, amount in sorted(mode_totals.items())
		],
		"total_amount": flt(sum(row["amount"] for row in rows)),
		"invoice_count": len(invoices),
	}


def _build_sales_report_xlsx(report, pos_profile, from_date, to_date, currency):
	from frappe.utils.xlsxutils import make_xlsx

	data = [
		[_("POS Sales Payment Report")],
		[_("POS Profile"), pos_profile],
		[_("Date Range"), f"{from_date} - {to_date}"],
		[
			_("Sales Person"),
			report["sales_person"] or _("All Sales Persons"),
		],
		[_("Currency"), currency],
		[],
		[
			_("Posting Date"),
			_("Invoice ID"),
			_("Sales Person"),
			_("Mode of Payment"),
			_("Amount"),
		],
	]
	for row in report["rows"]:
		data.append(
			[
				str(row["posting_date"]),
				row["invoice_id"],
				row["sales_person"],
				row["mode_of_payment"],
				flt(row["amount"]),
			]
		)

	data.extend([[], [_("Totals by Mode of Payment")]])
	for total in report["mode_totals"]:
		data.append(
			["", "", "", total["mode_of_payment"], flt(total["amount"])]
		)
	data.extend(
		[
			["", "", "", _("Overall Total"), flt(report["total_amount"])],
			["", "", "", _("Invoices"), cint(report["invoice_count"])],
		]
	)
	return make_xlsx(
		data,
		_("POS Sales Report"),
		column_widths=[16, 24, 24, 24, 18],
	).getvalue()


def _build_sales_report_pdf(report, pos_profile, from_date, to_date, currency):
	from frappe.utils.pdf import get_pdf

	rows_html = "".join(
		f"""
		<tr>
			<td>{escape(str(row["posting_date"]))}</td>
			<td>{escape(cstr(row["invoice_id"]))}</td>
			<td>{escape(cstr(row["sales_person"]))}</td>
			<td>{escape(cstr(row["mode_of_payment"]))}</td>
			<td class="amount">{escape(fmt_money(row["amount"], currency=currency))}</td>
		</tr>
		"""
		for row in report["rows"]
	)
	totals_html = "".join(
		f"""
		<tr>
			<td colspan="4">{escape(cstr(total["mode_of_payment"]))}</td>
			<td class="amount">{escape(fmt_money(total["amount"], currency=currency))}</td>
		</tr>
		"""
		for total in report["mode_totals"]
	)
	html = f"""
	<!doctype html>
	<html>
	<head>
		<meta charset="utf-8">
		<style>
			@page {{ size: A4; margin: 18mm 14mm; }}
			body {{ color: #1f2937; font-family: sans-serif; font-size: 10pt; }}
			h1 {{ font-size: 18pt; margin: 0 0 6px; }}
			.meta {{ color: #4b5563; margin-bottom: 18px; }}
			table {{ border-collapse: collapse; width: 100%; }}
			th, td {{ border: 1px solid #d1d5db; padding: 7px 8px; }}
			th {{ background: #f3f4f6; text-align: left; }}
			.amount {{ text-align: right; white-space: nowrap; }}
			.totals {{ margin-top: 16px; }}
			.totals td {{ font-weight: 600; }}
			.overall td {{ background: #f3f4f6; font-weight: 700; }}
		</style>
	</head>
	<body>
		<h1>{escape(_("POS Sales Payment Report"))}</h1>
		<div class="meta">
			<div>{escape(_("POS Profile"))}: {escape(cstr(pos_profile))}</div>
			<div>{escape(_("Date Range"))}: {escape(str(from_date))} - {escape(str(to_date))}</div>
			<div>{escape(_("Sales Person"))}: {escape(report["sales_person"] or _("All Sales Persons"))}</div>
			<div>{escape(_("Invoices"))}: {cint(report["invoice_count"])}</div>
		</div>
		<table>
			<thead>
				<tr>
					<th>{escape(_("Posting Date"))}</th>
					<th>{escape(_("Invoice ID"))}</th>
					<th>{escape(_("Sales Person"))}</th>
					<th>{escape(_("Mode of Payment"))}</th>
					<th class="amount">{escape(_("Amount"))}</th>
				</tr>
			</thead>
			<tbody>{rows_html}</tbody>
		</table>
		<table class="totals">
			<tbody>
				{totals_html}
				<tr class="overall">
					<td colspan="4">{escape(_("Overall Total"))}</td>
					<td class="amount">{escape(fmt_money(report["total_amount"], currency=currency))}</td>
				</tr>
			</tbody>
		</table>
	</body>
	</html>
	"""
	return get_pdf(html)


@frappe.whitelist()
def export_sales_report(
	pos_profile,
	from_date=None,
	to_date=None,
	file_type="xlsx",
	sales_person=None,
):
	"""Download a payment-level POS sales report for an accessible profile."""
	from_date, to_date = _validate_sales_report_access(
		pos_profile,
		from_date,
		to_date,
	)
	file_type = cstr(file_type).lower()
	if file_type not in {"xlsx", "pdf"}:
		frappe.throw(_("Export format must be Excel or PDF"))

	if not can_view_cash_report_figures():
		frappe.throw(_("Only Sales Manager can export cash/payment reports."), frappe.PermissionError)

	report = _get_sales_report_payment_export(
		pos_profile,
		from_date,
		to_date,
		sales_person=sales_person,
	)
	currency = (
		frappe.db.get_value("POS Profile", pos_profile, "currency")
		or frappe.defaults.get_global_default("currency")
		or ""
	)
	filename = (
		f"pos-sales-{frappe.scrub(pos_profile).replace('_', '-')}-{from_date}-to-{to_date}.{file_type}"
	)

	if file_type == "xlsx":
		filecontent = _build_sales_report_xlsx(
			report,
			pos_profile,
			from_date,
			to_date,
			currency,
		)
		response_type = "binary"
	else:
		filecontent = _build_sales_report_pdf(
			report,
			pos_profile,
			from_date,
			to_date,
			currency,
		)
		response_type = "pdf"

	frappe.local.response.filename = filename
	frappe.local.response.filecontent = filecontent
	frappe.local.response.type = response_type


@frappe.whitelist()
def get_sales_report(
	pos_profile,
	from_date=None,
	to_date=None,
	limit=10,
	sales_person=None,
):
	"""Return POS sales report metrics for the selected profile and date range."""
	from_date, to_date = _validate_sales_report_access(
		pos_profile,
		from_date,
		to_date,
	)
	limit = cint(limit) or 10

	cash_figures_visible = can_view_cash_report_figures()
	params = {
		"pos_profile": pos_profile,
		"from_date": from_date,
		"to_date": to_date,
		"limit": limit,
		"sales_person": cstr(sales_person).strip(),
	}

	filters = """
		si.pos_profile = %(pos_profile)s
		AND si.docstatus = 1
		AND si.is_pos = 1
		AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
		AND (
			%(sales_person)s = ''
			OR EXISTS (
				SELECT 1
				FROM `tabSales Team` sales_team_filter
				WHERE sales_team_filter.parent = si.name
					AND sales_team_filter.parenttype = 'Sales Invoice'
					AND sales_team_filter.sales_person = %(sales_person)s
			)
		)
	"""

	sales_persons = frappe.db.sql(
		"""
		SELECT DISTINCT sales_team.sales_person
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Team` sales_team
			ON sales_team.parent = si.name
			AND sales_team.parenttype = 'Sales Invoice'
		WHERE si.pos_profile = %(pos_profile)s
			AND si.docstatus = 1
			AND si.is_pos = 1
		ORDER BY sales_team.sales_person
		""",
		{"pos_profile": pos_profile},
		as_dict=True,
	)

	summary = frappe.db.sql(
		f"""
		SELECT
			COUNT(*) as invoice_count,
			SUM(CASE WHEN si.is_return = 0 THEN 1 ELSE 0 END) as sale_count,
			SUM(CASE WHEN si.is_return = 1 THEN 1 ELSE 0 END) as return_count,
			COALESCE(SUM(CASE WHEN si.is_return = 0 THEN si.grand_total ELSE 0 END), 0) as gross_sales,
			COALESCE(SUM(CASE WHEN si.is_return = 1 THEN ABS(si.grand_total) ELSE 0 END), 0) as returns_total,
			COALESCE(SUM(si.grand_total), 0) as net_sales,
			COALESCE(SUM(si.paid_amount), 0) as paid_amount,
			COALESCE(SUM(si.outstanding_amount), 0) as outstanding_amount,
			COALESCE(SUM(si.discount_amount), 0) as discount_amount
		FROM `tabSales Invoice` si
		WHERE {filters}
		""",
		params,
		as_dict=True,
	)[0]

	items_summary = frappe.db.sql(
		f"""
		SELECT
			COALESCE(SUM(sii.qty), 0) as quantity,
			COALESCE(SUM(sii.amount), 0) as amount
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE {filters}
			AND si.is_return = 0
		""",
		params,
		as_dict=True,
	)[0]

	top_items = frappe.db.sql(
		f"""
		SELECT
			sii.item_code,
			MAX(sii.item_name) as item_name,
			COALESCE(SUM(sii.qty), 0) as quantity,
			COALESCE(SUM(sii.amount), 0) as amount,
			COUNT(DISTINCT si.name) as invoice_count
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE {filters}
			AND si.is_return = 0
		GROUP BY sii.item_code
		ORDER BY amount DESC
		LIMIT %(limit)s
		""",
		params,
		as_dict=True,
	)

	inline_payments = frappe.db.sql(
		f"""
		SELECT
			sip.mode_of_payment,
			COALESCE(SUM(sip.amount), 0) as amount,
			COUNT(*) as count
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Payment` sip ON sip.parent = si.name
		WHERE {filters}
			AND sip.amount != 0
		GROUP BY sip.mode_of_payment
		""",
		params,
		as_dict=True,
	)

	payment_entries = frappe.db.sql(
		f"""
		SELECT
			pe.mode_of_payment,
			COALESCE(SUM(per.allocated_amount), 0) as amount,
			COUNT(DISTINCT pe.name) as count
		FROM `tabSales Invoice` si
		INNER JOIN `tabPayment Entry Reference` per
			ON per.reference_doctype = 'Sales Invoice'
			AND per.reference_name = si.name
		INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
		WHERE {filters}
			AND pe.docstatus = 1
		GROUP BY pe.mode_of_payment
		""",
		params,
		as_dict=True,
	)

	payment_map = {}
	for row in list(inline_payments or []) + list(payment_entries or []):
		mode = row.get("mode_of_payment") or _("Unspecified")
		if mode not in payment_map:
			payment_map[mode] = {"mode_of_payment": mode, "amount": 0, "count": 0}
		payment_map[mode]["amount"] += flt(row.get("amount"))
		payment_map[mode]["count"] += cint(row.get("count"))

	payment_methods = (
		sorted(
			payment_map.values(),
			key=lambda row: row.get("amount") or 0,
			reverse=True,
		)
		if cash_figures_visible
		else []
	)

	recent_invoices = frappe.db.sql(
		f"""
		SELECT
			si.name,
			si.customer,
			si.customer_name,
			si.posting_date,
			si.posting_time,
			si.grand_total,
			si.paid_amount,
			si.outstanding_amount,
			si.status,
			si.is_return,
			(
				SELECT GROUP_CONCAT(
					DISTINCT sales_team.sales_person
					ORDER BY sales_team.sales_person
					SEPARATOR ', '
				)
				FROM `tabSales Team` sales_team
				WHERE sales_team.parent = si.name
					AND sales_team.parenttype = 'Sales Invoice'
			) AS sales_person
		FROM `tabSales Invoice` si
		WHERE {filters}
		ORDER BY si.posting_date DESC, si.posting_time DESC
		LIMIT %(limit)s
		""",
		params,
		as_dict=True,
	)

	if not cash_figures_visible:
		for invoice in recent_invoices:
			invoice.paid_amount = None
			invoice.outstanding_amount = None

	return {
		"from_date": from_date,
		"to_date": to_date,
		"cash_figures_visible": cash_figures_visible,
		"summary": {
			"invoice_count": cint(summary.get("invoice_count")),
			"sale_count": cint(summary.get("sale_count")),
			"return_count": cint(summary.get("return_count")),
			"gross_sales": flt(summary.get("gross_sales")),
			"returns_total": flt(summary.get("returns_total")),
			"net_sales": flt(summary.get("net_sales")),
			"paid_amount": flt(summary.get("paid_amount")) if cash_figures_visible else None,
			"outstanding_amount": flt(summary.get("outstanding_amount")) if cash_figures_visible else None,
			"discount_amount": flt(summary.get("discount_amount")),
			"quantity": flt(items_summary.get("quantity")),
			"items_total": flt(items_summary.get("amount")),
		},
		"payment_methods": payment_methods,
		"sales_persons": [
			row.sales_person for row in sales_persons if row.sales_person
		],
		"top_items": top_items,
		"recent_invoices": recent_invoices,
	}


# ==========================================
# Draft Invoice Management
# ==========================================


@frappe.whitelist()
def get_draft_invoices(pos_opening_shift, doctype="Sales Invoice"):
    """Get all draft invoices for a POS opening shift."""
    filters = {
        "docstatus": 0,
    }

    # Add pos_opening_shift filter if the field exists
    if frappe.db.has_column(doctype, "pos_opening_shift"):
        filters["pos_opening_shift"] = pos_opening_shift

    # Performance: Get all invoice names first
    invoices_list = frappe.get_list(
        doctype,
        filters=filters,
        fields=["name"],
        limit_page_length=0,
        order_by="modified desc",
    )

    # Performance: Batch load all documents at once using get_cached_doc
    # This leverages Frappe's internal caching and is faster than individual queries
    data = []
    for invoice in invoices_list:
        data.append(frappe.get_cached_doc(doctype, invoice["name"]))

    return data


@frappe.whitelist()
def delete_invoice(invoice):
    """Delete draft invoice."""
    doctype = "Sales Invoice"

    if not frappe.db.exists(doctype, invoice):
        frappe.throw(_("Invoice {0} does not exist").format(invoice))

    # Check if it's a draft
    if frappe.db.get_value(doctype, invoice, "docstatus") != 0:
        frappe.throw(_("Cannot delete submitted invoice {0}").format(invoice))

    frappe.delete_doc(doctype, invoice, force=1)
    return _("Invoice {0} Deleted").format(invoice)


@frappe.whitelist()
def cleanup_old_drafts(pos_profile=None, max_age_hours=24):
    """
    Clean up old draft invoices to prevent stock reservation issues.
    Deletes drafts older than max_age_hours (default 24 hours).
    """
    from datetime import datetime, timedelta

    doctype = "Sales Invoice"
    cutoff_time = datetime.now() - timedelta(hours=int(max_age_hours))

    filters = {
        "docstatus": 0,  # Draft only
        "modified": ["<", cutoff_time.strftime("%Y-%m-%d %H:%M:%S")],
    }

    # Optionally filter by POS profile
    if pos_profile:
        filters["pos_profile"] = pos_profile

    # Get old drafts
    old_drafts = frappe.get_all(
        doctype,
        filters=filters,
        fields=["name", "modified"],
        limit_page_length=100,  # Safety limit
    )

    deleted_count = 0
    for draft in old_drafts:
        try:
            frappe.delete_doc(
                doctype, draft["name"], force=True, ignore_permissions=True
            )
            deleted_count += 1
        except Exception as e:
            frappe.log_error(
                f"Failed to delete draft {draft['name']}: {str(e)}",
                "Draft Cleanup Error",
            )

    if deleted_count > 0:
        frappe.db.commit()

    return {
        "deleted": deleted_count,
        "message": f"Cleaned up {deleted_count} old draft invoices",
    }


# ==========================================
# Return Invoice Management
# ==========================================


@frappe.whitelist()
def get_returnable_invoices(limit=50):
    """Get list of invoices that have items available for return."""
    # Performance: Use SQL aggregation to calculate returned quantities in one query
    # This eliminates N+1 queries by joining return invoices and aggregating in the database

    query = """
        SELECT
            si.name,
            si.customer,
            si.customer_name,
            si.posting_date,
            si.grand_total,
            si.status,
            COALESCE(SUM(CASE WHEN ret_item.qty IS NOT NULL THEN ABS(ret_item.qty) ELSE 0 END), 0) as total_returned_qty,
            COALESCE(SUM(CASE WHEN si_item.qty IS NOT NULL THEN si_item.qty ELSE 0 END), 0) as total_original_qty
        FROM `tabSales Invoice` si
        LEFT JOIN `tabSales Invoice Item` si_item ON si_item.parent = si.name
        LEFT JOIN `tabSales Invoice` ret_si ON ret_si.return_against = si.name
            AND ret_si.docstatus = 1
            AND ret_si.is_return = 1
        LEFT JOIN `tabSales Invoice Item` ret_item ON ret_item.parent = ret_si.name
            AND (ret_item.sales_invoice_item = si_item.name OR ret_item.item_code = si_item.item_code)
        WHERE si.docstatus = 1
            AND si.is_return = 0
            AND si.is_pos = 1
        GROUP BY si.name
        HAVING total_original_qty > total_returned_qty
        ORDER BY si.posting_date DESC, si.creation DESC
        LIMIT %s
    """

    returnable_invoices = frappe.db.sql(query, [cint(limit)], as_dict=1)

    return returnable_invoices


@frappe.whitelist()
def get_invoice_for_return(invoice_name):
    """Get invoice with return tracking - calculates remaining qty for each item."""
    if not frappe.db.exists("Sales Invoice", invoice_name):
        frappe.throw(_("Invoice {0} does not exist").format(invoice_name))

    # Get the original invoice
    invoice = frappe.get_doc("Sales Invoice", invoice_name)

    # Performance: Use SQL aggregation to calculate returned quantities in one query
    # This eliminates N+1 queries by aggregating all return items at once
    returned_qty_query = """
        SELECT
            COALESCE(ret_item.sales_invoice_item, ret_item.item_code) as key_field,
            SUM(ABS(ret_item.qty)) as returned_qty
        FROM `tabSales Invoice` ret_si
        INNER JOIN `tabSales Invoice Item` ret_item ON ret_item.parent = ret_si.name
        WHERE ret_si.return_against = %s
            AND ret_si.docstatus = 1
            AND ret_si.is_return = 1
        GROUP BY key_field
    """

    returned_qty_results = frappe.db.sql(returned_qty_query, [invoice_name], as_dict=1)
    returned_qty = {row["key_field"]: row["returned_qty"] for row in returned_qty_results}

    # Calculate remaining quantities
    invoice_dict = invoice.as_dict()
    updated_items = []

    for item in invoice_dict.get("items", []):
        # Check how much has been returned using the item's name (row ID)
        already_returned = returned_qty.get(item.name, 0)
        remaining_qty = item.qty - already_returned

        if remaining_qty > 0:
            item_copy = item.copy()
            item_copy["original_qty"] = item.qty
            item_copy["qty"] = remaining_qty
            item_copy["already_returned"] = already_returned
            updated_items.append(item_copy)

    invoice_dict["items"] = updated_items
    return invoice_dict


@frappe.whitelist()
def search_invoices_for_return(
    invoice_name=None,
    company=None,
    customer_name=None,
    customer_id=None,
    mobile_no=None,
    from_date=None,
    to_date=None,
    min_amount=None,
    max_amount=None,
    page=1,
    doctype="Sales Invoice",
):
    """Search for invoices that can be returned with pagination."""
    # Start with base filters
    filters = {
        "docstatus": 1,
        "is_return": 0,
    }

    if company:
        filters["company"] = company

    # Convert page to integer
    if page and isinstance(page, str):
        page = int(page)
    else:
        page = 1

    # Items per page
    page_length = 100
    start = (page - 1) * page_length

    # Add invoice name filter
    if invoice_name:
        filters["name"] = ["like", f"%{invoice_name}%"]

    # Add date range filters
    if from_date:
        filters["posting_date"] = [">=", from_date]

    if to_date:
        if "posting_date" in filters:
            filters["posting_date"] = ["between", [from_date, to_date]]
        else:
            filters["posting_date"] = ["<=", to_date]

    # Add amount filters
    if min_amount:
        filters["grand_total"] = [">=", float(min_amount)]

    if max_amount:
        if "grand_total" in filters:
            filters["grand_total"] = ["between", [float(min_amount), float(max_amount)]]
        else:
            filters["grand_total"] = ["<=", float(max_amount)]

    # If any customer search criteria is provided, find matching customers
    customer_ids = []
    if customer_name or customer_id or mobile_no:
        conditions = []
        params = {}

        if customer_name:
            conditions.append("customer_name LIKE %(customer_name)s")
            params["customer_name"] = f"%{customer_name}%"

        if customer_id:
            conditions.append("name LIKE %(customer_id)s")
            params["customer_id"] = f"%{customer_id}%"

        if mobile_no:
            conditions.append("mobile_no LIKE %(mobile_no)s")
            params["mobile_no"] = f"%{mobile_no}%"

        where_clause = " OR ".join(conditions)
        customer_query = f"""
			SELECT name
			FROM `tabCustomer`
			WHERE {where_clause}
			LIMIT 100
		"""

        customers = frappe.db.sql(customer_query, params, as_dict=True)
        customer_ids = [c.name for c in customers]

        if customer_ids:
            filters["customer"] = ["in", customer_ids]
        elif any([customer_name, customer_id, mobile_no]):
            return {"invoices": [], "has_more": False}

    # Count total invoices
    total_count_query = frappe.get_list(
        doctype,
        filters=filters,
        fields=["count(name) as total_count"],
        as_list=False,
    )
    total_count = total_count_query[0].total_count if total_count_query else 0

    # Get invoices with pagination
    invoices_list = frappe.get_list(
        doctype,
        filters=filters,
        fields=["name"],
        limit_start=start,
        limit_page_length=page_length,
        order_by="posting_date desc, name desc",
    )

    if not invoices_list:
        return {"invoices": [], "has_more": False}

    # Performance: Batch query all returned quantities for all invoices at once
    # This eliminates N+1 queries by aggregating return data in a single SQL call
    invoice_names = [inv["name"] for inv in invoices_list]

    returned_qty_query = """
        SELECT
            ret_si.return_against as invoice_name,
            ret_item.item_code,
            SUM(ABS(ret_item.qty)) as returned_qty
        FROM `tabSales Invoice` ret_si
        INNER JOIN `tabSales Invoice Item` ret_item ON ret_item.parent = ret_si.name
        WHERE ret_si.return_against IN %s
            AND ret_si.docstatus = 1
            AND ret_si.is_return = 1
        GROUP BY ret_si.return_against, ret_item.item_code
    """

    returned_qty_results = frappe.db.sql(returned_qty_query, [invoice_names], as_dict=1)

    # Build a map of invoice_name -> {item_code: returned_qty}
    returned_qty_map = {}
    for row in returned_qty_results:
        inv_name = row["invoice_name"]
        if inv_name not in returned_qty_map:
            returned_qty_map[inv_name] = {}
        returned_qty_map[inv_name][row["item_code"]] = row["returned_qty"]

    # Process and return results
    data = []

    for invoice in invoices_list:
        invoice_doc = frappe.get_doc(doctype, invoice.name)
        returned_qty = returned_qty_map.get(invoice.name, {})

        if returned_qty:
            # Filter items with remaining qty
            filtered_items = []
            for item in invoice_doc.items:
                already_returned = returned_qty.get(item.item_code, 0)
                remaining_qty = item.qty - already_returned

                if remaining_qty > 0:
                    new_item = item.as_dict().copy()
                    new_item["qty"] = remaining_qty
                    new_item["amount"] = remaining_qty * item.rate
                    if item.get("stock_qty"):
                        new_item["stock_qty"] = (
                            item.stock_qty / item.qty * remaining_qty
                            if item.qty
                            else remaining_qty
                        )
                    filtered_items.append(frappe._dict(new_item))

            if filtered_items:
                filtered_invoice = frappe.get_doc(doctype, invoice.name)
                filtered_invoice.items = filtered_items
                data.append(filtered_invoice)
        else:
            data.append(invoice_doc)

    # Check if there are more results
    has_more = (start + page_length) < total_count

    return {"invoices": data, "has_more": has_more}


# ==========================================
# Legacy/Helper Functions
# ==========================================


@frappe.whitelist()
def apply_offers(invoice_data, selected_offers=None):
    """Calculate and apply promotional offers using ERPNext Pricing Rules.

    Args:
            invoice_data (str | dict): Sales Invoice payload used for offer evaluation.
            selected_offers (str | list | None): Optional collection of Pricing Rule names.
                    When provided, results are filtered to only include these rules.
                    ERPNext handles all conflict resolution based on priority.
    """
    try:
        if isinstance(invoice_data, str):
            invoice_data = json.loads(invoice_data or "{}")

        invoice = frappe._dict(invoice_data or {})
        items = invoice.get("items") or []

        if isinstance(selected_offers, str):
            try:
                selected_offers = json.loads(selected_offers)
            except ValueError:
                selected_offers = [selected_offers]

        if isinstance(selected_offers, (list, tuple, set)):
            selected_offer_names = {
                cstr(name) for name in selected_offers if cstr(name)
            }
        else:
            selected_offer_names = set()

        if not items:
            return {"items": []}

        if not invoice.get("pos_profile") or not erpnext_apply_pricing_rule:
            # Either no POS profile supplied or ERPNext promotional engine unavailable
            return {"items": items}

        profile = frappe.get_doc("POS Profile", invoice.get("pos_profile"))

        pricing_items = []
        index_map = []
        prepared_items = [frappe._dict(row) for row in items]

        for idx, item in enumerate(prepared_items):
            item_code = item.get("item_code")
            qty = flt(item.get("qty") or item.get("quantity") or 0)

            if not item_code or qty <= 0:
                continue

            try:
                cached = frappe.get_cached_value(
                    "Item",
                    item_code,
                    ["item_name", "item_group", "brand", "stock_uom"],
                    as_dict=1,
                )
            except frappe.DoesNotExistError:
                cached = None

            conversion_factor = flt(item.get("conversion_factor") or 1) or 1
            price_list_rate = flt(item.get("price_list_rate") or item.get("rate") or 0)

            pricing_items.append(
                frappe._dict(
                    {
                        "doctype": "Sales Invoice Item",
                        "name": item.get("name") or f"POS-{idx}",
                        "item_code": item_code,
                        "item_name": (
                            cached.item_name if cached else item.get("item_name")
                        ),
                        "item_group": (
                            cached.item_group if cached else item.get("item_group")
                        ),
                        "brand": (cached.brand if cached else item.get("brand")),
                        "qty": qty,
                        "stock_qty": qty * conversion_factor,
                        "conversion_factor": conversion_factor,
                        "uom": item.get("uom")
                        or item.get("stock_uom")
                        or (cached.stock_uom if cached else None),
                        "stock_uom": item.get("stock_uom")
                        or (cached.stock_uom if cached else None),
                        "price_list_rate": price_list_rate,
                        "base_price_list_rate": price_list_rate,
                        "rate": flt(item.get("rate") or price_list_rate),
                        "base_rate": flt(item.get("rate") or price_list_rate),
                        "discount_percentage": 0,
                        "discount_amount": 0,
                        "warehouse": item.get("warehouse") or profile.warehouse,
                        "parenttype": invoice.get("doctype") or "Sales Invoice",
                    }
                )
            )
            index_map.append(idx)

            # Clear previously applied promotional metadata if the
            # current quantity can no longer satisfy the rule.
            item.discount_percentage = 0
            item.discount_amount = 0
            item.pricing_rules = []
            item.applied_promotional_schemes = []

        if not pricing_items:
            return {"items": items}

        company_currency = frappe.get_cached_value(
            "Company", profile.company, "default_currency"
        )

        # Get customer details if customer is provided
        customer = invoice.get("customer")
        customer_group = invoice.get("customer_group")
        territory = invoice.get("territory")

        if customer and not customer_group:
            # Fetch customer_group from customer
            try:
                customer_data = frappe.get_cached_value(
                    "Customer", customer, ["customer_group", "territory"], as_dict=1
                )
                if customer_data:
                    customer_group = customer_data.get("customer_group")
                    if not territory:
                        territory = customer_data.get("territory")
            except Exception:
                pass

        # If still no customer_group, use default
        if not customer_group:
            customer_group = "All Customer Groups"

        pricing_args = frappe._dict(
            {
                "doctype": invoice.get("doctype") or "Sales Invoice",
                "name": invoice.get("name") or "POS-INVOICE",
                "company": profile.company,
                "transaction_date": invoice.get("posting_date") or nowdate(),
                "posting_date": invoice.get("posting_date") or nowdate(),
                "currency": invoice.get("currency")
                or profile.get("currency")
                or company_currency,
                "conversion_rate": flt(invoice.get("conversion_rate") or 1) or 1,
                "plc_conversion_rate": flt(invoice.get("plc_conversion_rate") or 1)
                or 1,
                "price_list": invoice.get("price_list")
                or resolve_profile_selling_price_list(
                    profile,
                    customer=customer,
                    customer_group=customer_group,
                    warehouse=(
                        invoice.get("items", [{}])[0].get("warehouse")
                        if invoice.get("items")
                        else profile.warehouse
                    ),
                ),
                "customer": customer,
                "customer_group": customer_group,
                "territory": territory,
                "items": pricing_items,
            }
        )

        # Call ERPNext pricing engine - it handles all conflicts based on priority
        pricing_results = erpnext_apply_pricing_rule(pricing_args) or []

        if not pricing_results:
            return {"items": items}

        raw_rule_names = set()
        for result in pricing_results:
            if not result:
                continue
            rules = []
            if erpnext_get_applied_pricing_rules:
                rules = erpnext_get_applied_pricing_rules(result.get("pricing_rules"))
            else:
                raw_rules = result.get("pricing_rules") or []
                if isinstance(raw_rules, str):
                    if raw_rules.startswith("["):
                        rules = json.loads(raw_rules)
                    else:
                        rules = [r.strip() for r in raw_rules.split(",") if r.strip()]
                elif isinstance(raw_rules, (list, tuple, set)):
                    rules = list(raw_rules)
            raw_rule_names.update(rules)

        rule_map = {}
        if raw_rule_names:
            rule_records = frappe.get_all(
                "Pricing Rule",
                filters={"name": ["in", list(raw_rule_names)]},
                fields=[
                    "name",
                    "promotional_scheme",
                    "coupon_code_based",
                    "promotional_scheme_id",
                    "price_or_product_discount",
                ],
            )
            for record in rule_records:
                if record.promotional_scheme and not record.coupon_code_based:
                    rule_map[record.name] = record

        if selected_offer_names:
            # Restrict available rules to the ones explicitly selected from the UI.
            rule_map = {
                name: details
                for name, details in rule_map.items()
                if name in selected_offer_names
            }

        if not rule_map:
            return {"items": items}

        applied_rules = set()
        free_items = []

        for result, item_index in zip(pricing_results, index_map):
            if not result:
                continue

            if erpnext_get_applied_pricing_rules:
                rule_names = erpnext_get_applied_pricing_rules(
                    result.get("pricing_rules")
                )
            else:
                raw_rules = result.get("pricing_rules") or []
                if isinstance(raw_rules, str):
                    if raw_rules.startswith("["):
                        rule_names = json.loads(raw_rules)
                    else:
                        rule_names = [
                            r.strip() for r in raw_rules.split(",") if r.strip()
                        ]
                elif isinstance(raw_rules, (list, tuple, set)):
                    rule_names = list(raw_rules)
                else:
                    rule_names = []

            applicable_rule_names = [
                name for name in rule_names or [] if name in rule_map
            ]

            if not applicable_rule_names:
                continue

            applied_rules.update(applicable_rule_names)

            item_doc = prepared_items[item_index]
            qty = flt(item_doc.get("qty") or item_doc.get("quantity") or 0)
            price_list_rate = flt(
                result.get("price_list_rate")
                or item_doc.get("price_list_rate")
                or item_doc.get("rate")
                or 0
            )

            # Get discount from result or fetch from pricing rule
            discount_percentage = flt(result.get("discount_percentage") or 0)
            per_unit_discount = flt(result.get("discount_amount") or 0)

            # If ERPNext didn't calculate discount (validate_applied_rule=1),
            # we need to fetch and apply it manually
            if (
                not discount_percentage
                and not per_unit_discount
                and applicable_rule_names
            ):
                for rule_name in applicable_rule_names:
                    rule_doc = rule_map.get(rule_name)
                    if not rule_doc:
                        continue

                    # Fetch full pricing rule to get discount values
                    full_rule = frappe.get_cached_doc("Pricing Rule", rule_name)

                    if (
                        full_rule.rate_or_discount == "Discount Percentage"
                        and full_rule.discount_percentage
                    ):
                        discount_percentage += flt(full_rule.discount_percentage)
                    elif (
                        full_rule.rate_or_discount == "Discount Amount"
                        and full_rule.discount_amount
                    ):
                        per_unit_discount += flt(full_rule.discount_amount)
                    elif full_rule.rate_or_discount == "Rate" and full_rule.rate:
                        # Apply fixed rate
                        price_list_rate = flt(full_rule.rate)

            line_discount_amount = 0
            if discount_percentage and qty and price_list_rate:
                line_discount_amount = price_list_rate * qty * discount_percentage / 100
            elif per_unit_discount and qty:
                line_discount_amount = per_unit_discount * qty
            else:
                line_discount_amount = per_unit_discount

            if (
                not discount_percentage
                and line_discount_amount
                and qty
                and price_list_rate
            ):
                base_amount = price_list_rate * qty
                if base_amount:
                    discount_percentage = (line_discount_amount / base_amount) * 100

            item_doc.discount_percentage = discount_percentage
            item_doc.discount_amount = line_discount_amount
            item_doc.price_list_rate = price_list_rate
            item_doc.rate = flt(item_doc.get("rate") or price_list_rate)
            item_doc.pricing_rules = applicable_rule_names

            item_doc.applied_promotional_schemes = list(
                {
                    rule_map[name].promotional_scheme
                    for name in applicable_rule_names
                    if rule_map[name].promotional_scheme
                }
            )

            for free_item in result.get("free_item_data") or []:
                rule_name = free_item.get("pricing_rules")
                if not rule_name or rule_name not in rule_map:
                    continue
                free_item_doc = frappe._dict(free_item)
                free_item_doc.applied_promotional_scheme = rule_map[
                    rule_name
                ].promotional_scheme
                free_items.append(free_item_doc)

        return {
            "items": [dict(item) for item in prepared_items],
            "free_items": [dict(item) for item in free_items],
            "applied_pricing_rules": sorted(applied_rules),
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Apply Offers Error")
        frappe.throw(_("Error applying offers: {0}").format(str(e)))

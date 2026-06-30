import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


FIELDNAME = "posa_client_transaction_id"


def execute():
    custom_field_name = f"Sales Invoice-{FIELDNAME}"
    if not frappe.db.exists("Custom Field", custom_field_name):
        create_custom_field(
            "Sales Invoice",
            {
                "fieldname": FIELDNAME,
                "label": "POS Client Transaction ID",
                "fieldtype": "Data",
                "length": 140,
                "insert_after": "posa_is_printed",
                "hidden": 1,
                "read_only": 1,
                "no_copy": 1,
                "print_hide": 1,
                "search_index": 1,
                "unique": 1,
                "description": "Stable browser-generated ID used to prevent duplicate POS invoices.",
            },
        )
    else:
        frappe.db.set_value(
            "Custom Field",
            custom_field_name,
            {
                "hidden": 1,
                "read_only": 1,
                "no_copy": 1,
                "print_hide": 1,
                "search_index": 1,
                "unique": 1,
            },
            update_modified=False,
        )

    frappe.clear_cache(doctype="Sales Invoice")
    frappe.db.add_unique(
        "Sales Invoice",
        [FIELDNAME],
        constraint_name="uniq_sales_invoice_pos_client_transaction",
    )

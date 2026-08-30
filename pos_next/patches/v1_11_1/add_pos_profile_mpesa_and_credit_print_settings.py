import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
    custom_fields = {
        "posa_mpesa_quick_pay_section": {
            "fieldname": "posa_mpesa_quick_pay_section",
            "label": "POS M-Pesa Quick Pay",
            "fieldtype": "Section Break",
            "insert_after": "posa_cash_mode_of_payment",
        },
        "posa_mpesa_business_shortcode": {
            "fieldname": "posa_mpesa_business_shortcode",
            "label": "M-Pesa Business Shortcode",
            "fieldtype": "Data",
            "insert_after": "posa_mpesa_quick_pay_section",
            "description": "Branch till/paybill business shortcode used to show only this POS Profile's pending Quick Pay M-Pesa payments. Leave blank to use the company Mpesa Settings shortcode.",
        },
    }

    for fieldname, field in custom_fields.items():
        name = f"POS Profile-{fieldname}"
        if frappe.db.exists("Custom Field", name):
            frappe.db.set_value("Custom Field", name, field, update_modified=False)
        else:
            create_custom_field("POS Profile", field)


    invoice_fields = {
        "posa_print_format": {
            "fieldname": "posa_print_format",
            "label": "POS Print Format",
            "fieldtype": "Link",
            "options": "Print Format",
            "insert_after": "posa_client_transaction_id",
            "hidden": 1,
            "read_only": 1,
            "allow_on_submit": 1,
            "no_copy": 1,
            "print_hide": 1,
            "description": "Print format selected from the POS Profile when this invoice was created.",
        },
        "posa_letter_head": {
            "fieldname": "posa_letter_head",
            "label": "POS Letter Head",
            "fieldtype": "Link",
            "options": "Letter Head",
            "insert_after": "posa_print_format",
            "hidden": 1,
            "read_only": 1,
            "allow_on_submit": 1,
            "no_copy": 1,
            "print_hide": 1,
            "description": "Letter head selected from the POS Profile when this invoice was created.",
        },
    }

    for fieldname, field in invoice_fields.items():
        name = f"Sales Invoice-{fieldname}"
        if frappe.db.exists("Custom Field", name):
            frappe.db.set_value("Custom Field", name, field, update_modified=False)
        else:
            create_custom_field("Sales Invoice", field)

    frappe.clear_cache(doctype="POS Profile")
    frappe.clear_cache(doctype="Sales Invoice")
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


FIELDNAME = "custom_company"


def execute():
    custom_field_name = f"Customer-{FIELDNAME}"
    if not frappe.db.exists("Custom Field", custom_field_name):
        create_custom_field(
            "Customer",
            {
                "fieldname": FIELDNAME,
                "label": "Company",
                "fieldtype": "Link",
                "options": "Company",
                "insert_after": "customer_group",
                "in_standard_filter": 1,
                "description": "Company used by POS Next to scope customer search per POS Profile",
            },
        )
    else:
        frappe.db.set_value(
            "Custom Field",
            custom_field_name,
            {
                "fieldtype": "Link",
                "options": "Company",
                "in_standard_filter": 1,
                "description": "Company used by POS Next to scope customer search per POS Profile",
            },
            update_modified=False,
        )

    frappe.clear_cache(doctype="Customer")

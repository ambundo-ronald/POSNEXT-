import frappe


@frappe.whitelist()
def get_pos_translations():
    """Return translations using the API available in the installed Frappe version."""
    from frappe import translate

    if hasattr(translate, "get_boot_translations"):
        return translate.get_boot_translations(frappe.local.lang)

    if hasattr(translate, "get_all_translations"):
        return translate.get_all_translations(frappe.local.lang)

    return translate.get_app_translations()

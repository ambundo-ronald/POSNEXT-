# Copyright (c) 2026, BrainWise and contributors
# For license information, please see license.txt

import frappe


DESK_ROUTE_PREFIXES = ("/app", "/desk")
POS_HOME_ROUTE = "/pos"
POS_LOGIN_ROUTE = "/pos/account/login"


def is_pos_only_user(user=None):
    user = user or frappe.session.user
    if not user or user == "Guest":
        return False

    return bool(frappe.db.get_value("User", user, "posa_pos_user_only"))


def is_desk_request(path):
    normalized_path = (path or "").strip() or "/"
    return any(
        normalized_path == prefix or normalized_path.startswith(f"{prefix}/")
        for prefix in DESK_ROUTE_PREFIXES
    )


def enforce_pos_only_access():
    if frappe.session.user == "Guest":
        return

    request = getattr(frappe.local, "request", None)
    if not request:
        return

    if not is_pos_only_user():
        return

    if not is_desk_request(request.path):
        return

    set_redirect(POS_HOME_ROUTE)


def set_redirect(location):
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = location


def redirect_pos_only_user_after_login(login_manager):
    user = getattr(login_manager, "user", None) or frappe.session.user
    if not is_pos_only_user(user):
        return

    set_redirect(POS_HOME_ROUTE)


def redirect_pos_only_user_after_logout(login_manager):
    user = getattr(login_manager, "user", None)
    if not is_pos_only_user(user):
        return

    set_redirect(POS_LOGIN_ROUTE)

# Copyright (c) 2026, BrainWise and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint


DESK_ROUTE_PREFIXES = ("/app", "/desk")
DESK_API_PREFIXES = ("/api/method/frappe.desk.", "/api/method/frappe.desk/")
POS_HOME_ROUTE = "/pos"
POS_LOGIN_ROUTE = "/pos/account/login"


def is_pos_only_user(user=None):
    user = user or frappe.session.user
    if not user or user == "Guest":
        return False

    return bool(cint(frappe.db.get_value("User", user, "posa_pos_user_only")))


def is_desk_request(path):
    normalized_path = (path or "").strip() or "/"
    return any(
        normalized_path == prefix or normalized_path.startswith(f"{prefix}/")
        for prefix in DESK_ROUTE_PREFIXES
    ) or any(normalized_path.startswith(prefix) for prefix in DESK_API_PREFIXES)


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

    redirect(POS_HOME_ROUTE, raise_exception=True)


def redirect(location, raise_exception=False):
    frappe.flags.redirect_location = location
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = location
    frappe.local.response["http_status_code"] = 302

    if raise_exception:
        raise frappe.Redirect


def redirect_pos_only_user_after_login(login_manager):
    user = getattr(login_manager, "user", None) or frappe.session.user
    if not is_pos_only_user(user):
        return

    redirect(POS_HOME_ROUTE)


def redirect_pos_only_user_after_logout(login_manager):
    user = getattr(login_manager, "user", None)
    if not is_pos_only_user(user):
        return

    redirect(POS_LOGIN_ROUTE)

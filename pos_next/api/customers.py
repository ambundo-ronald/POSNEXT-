"""
POS Next Customer API
Handles customer search, creation, and management for POS operations
"""

import frappe
from frappe import _


CUSTOMER_COMPANY_FIELD = "custom_company"


def _customer_has_company_field():
    return frappe.db.has_column("Customer", CUSTOMER_COMPANY_FIELD)


def _get_pos_profile_doc(pos_profile):
    if not pos_profile:
        return None

    if isinstance(pos_profile, dict):
        pos_profile = pos_profile.get("name") or pos_profile.get("pos_profile")

    if not pos_profile:
        return None

    return frappe.get_cached_doc("POS Profile", pos_profile)


def _get_pos_customer_scope(profile_doc):
    if not profile_doc:
        return None, None

    return profile_doc.company, getattr(profile_doc, "customer", None)


@frappe.whitelist()
def get_customers(search_term="", pos_profile=None, start=0, limit=20):

    """
    Search customers for inline customer selection in POS.

    Args:
        search_term (str): Search query (name, mobile, or customer ID)
        pos_profile (str): POS Profile to filter by customer group
        start (int): Offset for paginated results
        limit (int): Maximum number of results to return

    Returns:
        list: List of customer dictionaries with name, customer_name, mobile_no, email_id
    """
    try:
        frappe.logger().debug(
            f"get_customers called with search_term={search_term}, pos_profile={pos_profile}, limit={limit}"
        )

        filters = {"disabled": 0}
        params = {}
        conditions = ["c.disabled = 0"]
        profile_doc = _get_pos_profile_doc(pos_profile)
        company, default_customer = _get_pos_customer_scope(profile_doc)

        # Filter by POS Profile customer group if specified
        if profile_doc and getattr(profile_doc, "customer_group", None):
            filters["customer_group"] = profile_doc.customer_group
            conditions.append("c.customer_group = %(customer_group)s")
            params["customer_group"] = profile_doc.customer_group
            frappe.logger().debug(f"Filtering by customer_group: {profile_doc.customer_group}")

        if search_term:
            conditions.append(
                """(
                    c.name LIKE %(search_term)s
                    OR c.customer_name LIKE %(search_term)s
                    OR c.mobile_no LIKE %(search_term)s
                    OR c.email_id LIKE %(search_term)s
                )"""
            )
            params["search_term"] = f"%{search_term}%"

        if company:
            params["company"] = company
            params["default_customer"] = default_customer or ""
            company_conditions = [
                """EXISTS (
                    SELECT 1
                    FROM `tabSales Invoice` si
                    WHERE si.customer = c.name
                        AND si.company = %(company)s
                        AND si.docstatus < 2
                )""",
            ]

            if default_customer:
                company_conditions.append("c.name = %(default_customer)s")

            if _customer_has_company_field():
                company_conditions.append(f"c.{CUSTOMER_COMPANY_FIELD} = %(company)s")

            conditions.append(f"({' OR '.join(company_conditions)})")

        customer_limit = int(limit or 0)
        if customer_limit <= 0:
            customer_limit = None

        fields = ["c.name", "c.customer_name", "c.mobile_no", "c.email_id", "c.customer_group"]
        if _customer_has_company_field():
            fields.append(f"c.{CUSTOMER_COMPANY_FIELD}")

        query = f"""
            SELECT {', '.join(fields)}
            FROM `tabCustomer` c
            WHERE {' AND '.join(conditions)}
            ORDER BY c.customer_name ASC
        """
        if customer_limit:
            query += " LIMIT %(limit)s OFFSET %(start)s"
            params["limit"] = customer_limit
            params["start"] = int(start or 0)

        result = frappe.db.sql(query, params, as_dict=True)
        frappe.logger().debug(f"get_customers returned {len(result)} customers")
        return result
    except Exception as e:
        frappe.logger().error(f"Error in get_customers: {str(e)}")
        frappe.logger().error(frappe.get_traceback())
        frappe.throw(_("Error fetching customers: {0}").format(str(e)))


@frappe.whitelist()
def create_customer(
    customer_name,
    mobile_no=None,
    email_id=None,
    customer_group="Individual",
    territory="All Territories",
    pos_profile=None,
):
    """
    Create a new customer from POS.

    Args:
        customer_name (str): Customer name (required)
        mobile_no (str): Mobile number (optional)
        email_id (str): Email address (optional)
        customer_group (str): Customer group (default: Individual)
        territory (str): Territory (default: All Territories)
        pos_profile (str): POS Profile used to tag the customer company

    Returns:
        dict: Created customer document
    """
    # Check if user has permission to create customers
    if not frappe.has_permission("Customer", "create"):
        frappe.throw(_("You don't have permission to create customers"), frappe.PermissionError)

    if not customer_name:
        frappe.throw(_("Customer name is required"))

    customer_data = {
        "doctype": "Customer",
        "customer_name": customer_name,
        "customer_type": "Individual",
        "customer_group": customer_group or "Individual",
        "territory": territory or "All Territories",
        "mobile_no": mobile_no or "",
        "email_id": email_id or "",
    }

    profile_doc = _get_pos_profile_doc(pos_profile)
    company, _default_customer = _get_pos_customer_scope(profile_doc)
    if company and _customer_has_company_field():
        customer_data[CUSTOMER_COMPANY_FIELD] = company

    customer = frappe.get_doc(customer_data)

    customer.insert()

    return customer.as_dict()


@frappe.whitelist()
def get_customer_details(customer):
    """
    Get detailed customer information.

    Args:
        customer (str): Customer ID

    Returns:
        dict: Customer details
    """
    if not customer:
        frappe.throw(_("Customer is required"))

    return frappe.get_cached_doc("Customer", customer).as_dict()

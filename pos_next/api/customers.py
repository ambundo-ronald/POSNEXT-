"""
POS Next Customer API
Handles customer search, creation, and management for POS operations
"""

import frappe
from frappe import _


@frappe.whitelist()
def get_customers(search_term="", pos_profile=None, start=0, limit=20):
    """
    Search customers for inline customer selection in POS.

    Args:
        search_term (str): Search query (name, mobile, or customer ID)
        pos_profile (str): POS Profile to filter by customer group and company
        start (int): Offset for paginated results
        limit (int): Maximum number of results to return

    Returns:
        list: List of customer dictionaries with name, customer_name, mobile_no, email_id
    """
    try:
        frappe.logger().debug(
            f"get_customers called with search_term={search_term}, pos_profile={pos_profile}, limit={limit}"
        )

        conditions = ["c.disabled = 0"]
        params = {}
        company = None
        default_customer = None

        if pos_profile:
            frappe.logger().debug(f"Loading POS Profile: {pos_profile}")
            profile_doc = frappe.get_cached_doc("POS Profile", pos_profile)
            company = profile_doc.company
            default_customer = getattr(profile_doc, "customer", None)

            if hasattr(profile_doc, "customer_group") and profile_doc.customer_group:
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
            company_conditions = [
                """EXISTS (
                    SELECT 1
                    FROM `tabParty Account` pa
                    WHERE pa.parenttype = 'Customer'
                        AND pa.parent = c.name
                        AND pa.company = %(company)s
                )""",
                """EXISTS (
                    SELECT 1
                    FROM `tabSales Invoice` si
                    WHERE si.customer = c.name
                        AND si.company = %(company)s
                        AND si.docstatus < 2
                )""",
            ]

            if default_customer:
                params["default_customer"] = default_customer
                company_conditions.append("c.name = %(default_customer)s")

            conditions.append(f"({' OR '.join(company_conditions)})")

        query = f"""
            SELECT
                c.name,
                c.customer_name,
                c.mobile_no,
                c.email_id,
                c.customer_group
            FROM `tabCustomer` c
            WHERE {' AND '.join(conditions)}
            ORDER BY c.customer_name ASC
        """

        customer_limit = int(limit or 0)
        if customer_limit > 0:
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
def create_customer(customer_name, mobile_no=None, email_id=None, customer_group="Individual", territory="All Territories"):
    """
    Create a new customer from POS.

    Args:
        customer_name (str): Customer name (required)
        mobile_no (str): Mobile number (optional)
        email_id (str): Email address (optional)
        customer_group (str): Customer group (default: Individual)
        territory (str): Territory (default: All Territories)

    Returns:
        dict: Created customer document
    """
    # Check if user has permission to create customers
    if not frappe.has_permission("Customer", "create"):
        frappe.throw(_("You don't have permission to create customers"), frappe.PermissionError)

    if not customer_name:
        frappe.throw(_("Customer name is required"))

    customer = frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": customer_name,
            "customer_type": "Individual",
            "customer_group": customer_group or "Individual",
            "territory": territory or "All Territories",
            "mobile_no": mobile_no or "",
            "email_id": email_id or "",
        }
    )

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
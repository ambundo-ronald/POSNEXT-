import json

import frappe


def parse_customer_context(customer=None, customer_group=None):
	"""Normalize customer inputs from plain strings or serialized objects."""
	if isinstance(customer, str):
		try:
			parsed = json.loads(customer)
		except Exception:
			parsed = None

		if isinstance(parsed, dict):
			customer_group = customer_group or parsed.get("customer_group")
			customer = parsed.get("name") or parsed.get("customer")

	if isinstance(customer, dict):
		customer_group = customer_group or customer.get("customer_group")
		customer = customer.get("name") or customer.get("customer")

	return customer, customer_group


def get_customer_group(customer=None, customer_group=None):
	"""Resolve customer group from explicit input or the customer master."""
	customer, customer_group = parse_customer_context(customer, customer_group)

	if customer_group:
		return customer_group

	if not customer:
		return None

	try:
		return frappe.get_cached_value("Customer", customer, "customer_group")
	except Exception:
		return None


def resolve_profile_selling_price_list(pos_profile, customer=None, customer_group=None, warehouse=None):
	"""
	Resolve the effective selling price list for a POS Profile.

	POS Settings conditional mappings are preferred when a warehouse and
	customer group match. When no mapping exists, the POS Profile customer-group
	table is used. Finally, the profile's default selling price list is returned.
	"""
	pos_profile_doc = (
		pos_profile
		if getattr(pos_profile, "doctype", None) == "POS Profile"
		else frappe.get_cached_doc("POS Profile", pos_profile)
	)

	default_price_list = getattr(pos_profile_doc, "selling_price_list", None)
	resolved_group = get_customer_group(customer=customer, customer_group=customer_group)
	resolved_warehouse = warehouse or getattr(pos_profile_doc, "warehouse", None)

	if resolved_group and resolved_warehouse:
		try:
			mapped_price_list = frappe.db.get_value(
				"POS Price List Mapping",
				{
					"pos_profile": pos_profile_doc.name,
					"warehouse": resolved_warehouse,
					"customer_group": resolved_group,
					"enabled": 1,
				},
				"price_list",
			)
			if mapped_price_list:
				return mapped_price_list
		except Exception:
			# Mapping doctype may not be installed on older sites. Fall back to
			# POS Profile pricing below.
			pass

	if not getattr(pos_profile_doc, "posa_enable_customer_group_price_lists", 0):
		return default_price_list

	if not resolved_group:
		return default_price_list

	for row in getattr(pos_profile_doc, "posa_customer_group_price_lists", []) or []:
		if row.customer_group == resolved_group and row.price_list:
			return row.price_list

	return default_price_list

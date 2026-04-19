# -*- coding: utf-8 -*-
# Copyright (c) 2025, POS Next and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _


def _has_pos_profile_access(pos_profile, permission):
	has_access = frappe.db.exists(
		"POS Profile User",
		{"parent": pos_profile, "user": frappe.session.user},
	)
	return has_access or frappe.has_permission("POS Price List Mapping", permission)


@frappe.whitelist()
def get_price_list_mappings(pos_profile=None):
	"""Fetch enabled conditional price-list mappings for a POS Profile."""
	if not pos_profile:
		frappe.throw(_("POS Profile is required"))

	if not _has_pos_profile_access(pos_profile, "read"):
		frappe.throw(_("You don't have access to this POS Profile"))

	return frappe.db.get_list(
		"POS Price List Mapping",
		filters={"pos_profile": pos_profile, "enabled": 1},
		fields=["name", "warehouse", "customer_group", "price_list"],
		order_by="warehouse asc",
	)


@frappe.whitelist()
def save_price_list_mapping(pos_profile, warehouse, customer_group, price_list):
	"""Create or update a conditional price-list mapping."""
	if not _has_pos_profile_access(pos_profile, "write"):
		frappe.throw(_("You don't have access to this POS Profile"))

	if not frappe.db.exists("Warehouse", warehouse):
		frappe.throw(_("Warehouse {0} does not exist").format(warehouse))

	if not frappe.db.exists("Customer Group", customer_group):
		frappe.throw(_("Customer Group {0} does not exist").format(customer_group))

	if not frappe.db.exists("Price List", price_list):
		frappe.throw(_("Price List {0} does not exist").format(price_list))

	existing = frappe.db.get_value(
		"POS Price List Mapping",
		{
			"pos_profile": pos_profile,
			"warehouse": warehouse,
			"customer_group": customer_group,
		},
	)

	if existing:
		doc = frappe.get_doc("POS Price List Mapping", existing)
		doc.price_list = price_list
		doc.enabled = 1
		doc.save()
	else:
		doc = frappe.new_doc("POS Price List Mapping")
		doc.pos_profile = pos_profile
		doc.warehouse = warehouse
		doc.customer_group = customer_group
		doc.price_list = price_list
		doc.enabled = 1
		doc.insert()

	frappe.db.commit()
	return {
		"success": True,
		"mapping": doc.as_dict(),
		"message": _("Mapping saved successfully"),
	}


@frappe.whitelist()
def delete_price_list_mapping(mapping_name):
	"""Delete a conditional price-list mapping."""
	doc = frappe.get_doc("POS Price List Mapping", mapping_name)

	if not _has_pos_profile_access(doc.pos_profile, "delete"):
		frappe.throw(_("You don't have access to this POS Profile"))

	doc.delete()
	frappe.db.commit()
	return {"success": True, "message": _("Mapping deleted successfully")}


@frappe.whitelist()
def resolve_price_list(pos_profile, warehouse, customer_group):
	"""Resolve a mapped price list for a warehouse and customer group."""
	if not all([pos_profile, warehouse, customer_group]):
		return None

	return frappe.db.get_value(
		"POS Price List Mapping",
		{
			"pos_profile": pos_profile,
			"warehouse": warehouse,
			"customer_group": customer_group,
			"enabled": 1,
		},
		"price_list",
	)

# -*- coding: utf-8 -*-
# Copyright (c) 2025, POS Next and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


@frappe.whitelist()
def get_price_list_mappings(pos_profile=None):
	"""
	Fetch price list mappings for a POS Profile.
	
	Used by the POS frontend to load conditional price list mappings.
	These mappings determine which price list to use based on:
	- Selected Warehouse
	- Customer's Group
	"""
	if not pos_profile:
		frappe.throw(_("POS Profile is required"))

	# Check if user has access to this POS Profile
	has_access = frappe.db.exists(
		"POS Profile User",
		{"parent": pos_profile, "user": frappe.session.user}
	)

	if not has_access and not frappe.has_permission("POS Price List Mapping", "read"):
		frappe.throw(_("You don't have access to this POS Profile"))

	mappings = frappe.db.get_list(
		"POS Price List Mapping",
		filters={"pos_profile": pos_profile, "enabled": 1},
		fields=["name", "warehouse", "customer_group", "price_list"],
		order_by="warehouse asc"
	)

	return mappings


@frappe.whitelist()
def save_price_list_mapping(pos_profile, warehouse, customer_group, price_list):
	"""
	Save or update a price list mapping.
	
	If a mapping already exists for the same warehouse + customer_group,
	it will be updated. Otherwise, a new one is created.
	"""
	# Check if user has access
	has_access = frappe.db.exists(
		"POS Profile User",
		{"parent": pos_profile, "user": frappe.session.user}
	)

	if not has_access and not frappe.has_permission("POS Price List Mapping", "write"):
		frappe.throw(_("You don't have access to this POS Profile"))

	# Validate inputs
	if not frappe.db.exists("Warehouse", warehouse):
		frappe.throw(_("Warehouse {0} does not exist").format(warehouse))

	if not frappe.db.exists("Customer Group", customer_group):
		frappe.throw(_("Customer Group {0} does not exist").format(customer_group))

	if not frappe.db.exists("Price List", price_list):
		frappe.throw(_("Price List {0} does not exist").format(price_list))

	# Check if mapping already exists
	existing = frappe.db.get_value(
		"POS Price List Mapping",
		{
			"pos_profile": pos_profile,
			"warehouse": warehouse,
			"customer_group": customer_group
		}
	)

	if existing:
		# Update existing
		doc = frappe.get_doc("POS Price List Mapping", existing)
		doc.price_list = price_list
		doc.save()
		frappe.db.commit()
		return {"success": True, "mapping": doc.as_dict(), "message": _("Mapping updated successfully")}
	else:
		# Create new
		doc = frappe.new_doc("POS Price List Mapping")
		doc.pos_profile = pos_profile
		doc.warehouse = warehouse
		doc.customer_group = customer_group
		doc.price_list = price_list
		doc.enabled = 1
		doc.insert()
		frappe.db.commit()
		return {"success": True, "mapping": doc.as_dict(), "message": _("Mapping created successfully")}


@frappe.whitelist()
def delete_price_list_mapping(mapping_name):
	"""
	Delete a price list mapping.
	"""
	doc = frappe.get_doc("POS Price List Mapping", mapping_name)
	
	# Check if user has access
	has_access = frappe.db.exists(
		"POS Profile User",
		{"parent": doc.pos_profile, "user": frappe.session.user}
	)

	if not has_access and not frappe.has_permission("POS Price List Mapping", "delete"):
		frappe.throw(_("You don't have access to this POS Profile"))

	doc.delete()
	frappe.db.commit()
	return {"success": True, "message": _("Mapping deleted successfully")}


@frappe.whitelist()
def resolve_price_list(pos_profile, warehouse, customer_group):
	"""
	Resolve the price list for given warehouse and customer group combination.
	
	This is called when:
	1. Customer is selected (have their group)
	2. Warehouse is selected (known)
	
	Returns the mapped price list if a mapping exists and is enabled.
	Otherwise returns None so the default logic applies.
	"""
	if not all([pos_profile, warehouse, customer_group]):
		return None

	mapping = frappe.db.get_value(
		"POS Price List Mapping",
		{
			"pos_profile": pos_profile,
			"warehouse": warehouse,
			"customer_group": customer_group,
			"enabled": 1
		},
		"price_list"
	)

	return mapping

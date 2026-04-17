# Copyright (c) 2025, POS Next and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class POSPriceListMapping(Document):
	"""
	Doctype for conditional Price List mapping based on Warehouse and Customer Group.
	
	Allows POS users to automatically apply specific price lists when:
	- A particular warehouse is selected
	- AND a customer from a specific customer group is selected
	
	Example:
	- Warehouse: Ruiru - LLL
	- Customer Group: Retail
	- Price List: Retail-Ruiru
	"""

	def validate(self):
		"""Validate POS Price List Mapping"""
		# Check if warehouse exists
		if not frappe.db.exists("Warehouse", self.warehouse):
			frappe.throw(_("Warehouse {0} does not exist").format(self.warehouse))

		# Check if customer group exists
		if not frappe.db.exists("Customer Group", self.customer_group):
			frappe.throw(_("Customer Group {0} does not exist").format(self.customer_group))

		# Check if price list exists
		if not frappe.db.exists("Price List", self.price_list):
			frappe.throw(_("Price List {0} does not exist").format(self.price_list))

		# Check for duplicate mappings (same warehouse + customer group)
		existing = frappe.db.get_value(
			"POS Price List Mapping",
			{
				"pos_profile": self.pos_profile,
				"warehouse": self.warehouse,
				"customer_group": self.customer_group,
				"name": ["!=", self.name]
			}
		)

		if existing:
			frappe.throw(
				_("Mapping already exists for Warehouse {0} and Customer Group {1}").format(
					self.warehouse, self.customer_group
				)
			)


@frappe.whitelist()
def get_price_list_mappings(pos_profile=None):
	"""
	Fetch price list mappings for a POS Profile.
	
	If pos_profile is not provided, returns all mappings for the current user's POS Profiles.
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
		filters={"pos_profile": pos_profile},
		fields=["name", "warehouse", "customer_group", "price_list", "enabled"],
		order_by="warehouse asc"
	)

	return mappings


@frappe.whitelist()
def save_price_list_mapping(pos_profile, warehouse, customer_group, price_list):
	"""
	Save or update a price list mapping.
	"""
	# Check if user has access
	has_access = frappe.db.exists(
		"POS Profile User",
		{"parent": pos_profile, "user": frappe.session.user}
	)

	if not has_access and not frappe.has_permission("POS Price List Mapping", "write"):
		frappe.throw(_("You don't have access to this POS Profile"))

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
		return doc
	else:
		# Create new
		doc = frappe.new_doc("POS Price List Mapping")
		doc.pos_profile = pos_profile
		doc.warehouse = warehouse
		doc.customer_group = customer_group
		doc.price_list = price_list
		doc.enabled = 1
		doc.insert()
		return doc


@frappe.whitelist()
def delete_price_list_mapping(name):
	"""
	Delete a price list mapping.
	"""
	doc = frappe.get_doc("POS Price List Mapping", name)
	
	# Check if user has access
	has_access = frappe.db.exists(
		"POS Profile User",
		{"parent": doc.pos_profile, "user": frappe.session.user}
	)

	if not has_access and not frappe.has_permission("POS Price List Mapping", "delete"):
		frappe.throw(_("You don't have access to this POS Profile"))

	doc.delete()
	return {"success": True, "message": _("Mapping deleted successfully")}


@frappe.whitelist()
def resolve_price_list(pos_profile, warehouse, customer_group):
	"""
	Resolve the price list for given warehouse and customer group combination.
	
	Returns the mapped price list if it exists, otherwise returns None.
	"""
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

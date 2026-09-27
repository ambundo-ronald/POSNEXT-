import json

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	from_date = getdate(filters.get("from_date") or nowdate())
	to_date = getdate(filters.get("to_date") or nowdate())
	if from_date > to_date:
		frappe.throw(_("From Date cannot be after To Date"))

	data = get_data(filters, from_date, to_date)
	append_total(data)
	return get_columns(), data


def get_columns():
	return [
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
		{"label": _("Invoice"), "fieldname": "invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 190},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 170},
		{"label": _("POS Profile"), "fieldname": "pos_profile", "fieldtype": "Link", "options": "POS Profile", "width": 160},
		{"label": _("Sales Person"), "fieldname": "sales_person", "fieldtype": "Link", "options": "Sales Person", "width": 170},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": _("Allocated Sales"), "fieldname": "allocated_sales", "fieldtype": "Currency", "width": 130},
		{"label": _("Item Share %"), "fieldname": "allocated_percentage", "fieldtype": "Percent", "width": 110},
		{"label": _("Commission %"), "fieldname": "commission_rate", "fieldtype": "Percent", "width": 110},
		{"label": _("Commission Amount"), "fieldname": "commission_amount", "fieldtype": "Currency", "width": 150},
	]


def get_data(filters, from_date, to_date):
	conditions = [
		"si.docstatus = 1",
		"si.posting_date BETWEEN %(from_date)s AND %(to_date)s",
		"IFNULL(sii.posa_sales_person, '') != ''",
	]
	params = {"from_date": from_date, "to_date": to_date}
	for field in ("company", "pos_profile"):
		if filters.get(field):
			conditions.append(f"si.{field} = %({field})s")
			params[field] = filters.get(field)
	if filters.get("item_group"):
		conditions.append("sii.item_group = %(item_group)s")
		params["item_group"] = filters.item_group

	rows = frappe.db.sql(
		f"""
		SELECT si.posting_date, si.name AS invoice, si.company, si.pos_profile,
			sii.item_code, sii.item_name, sii.amount, sii.posa_sales_person,
			sii.posa_commission_rate, sii.posa_commission_amount,
			sii.posa_sales_person_allocations
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE {" AND ".join(conditions)}
		ORDER BY si.posting_date, si.name, sii.idx
		""",
		params,
		as_dict=True,
	)

	data = []
	for row in rows:
		allocations = parse_allocations(row.posa_sales_person_allocations)
		if allocations:
			for allocation in allocations:
				append_allocation(data, row, allocation, filters.get("sales_person"))
		else:
			allocation = {
				"sales_person": row.posa_sales_person,
				"allocated_percentage": 100,
				"allocated_amount": row.amount,
				"commission_rate": row.posa_commission_rate,
				"commission_amount": row.posa_commission_amount,
			}
			append_allocation(data, row, allocation, filters.get("sales_person"))
	return data


def parse_allocations(value):
	if not value:
		return []
	try:
		rows = json.loads(value)
		return rows if isinstance(rows, list) else []
	except (TypeError, ValueError):
		return []


def append_allocation(data, row, allocation, sales_person_filter=None):
	sales_person = allocation.get("sales_person")
	if not sales_person or (sales_person_filter and sales_person != sales_person_filter):
		return
	data.append({
		"posting_date": row.posting_date,
		"invoice": row.invoice,
		"company": row.company,
		"pos_profile": row.pos_profile,
		"sales_person": sales_person,
		"item_code": row.item_code,
		"item_name": row.item_name,
		"allocated_sales": flt(allocation.get("allocated_amount"), 2),
		"allocated_percentage": flt(allocation.get("allocated_percentage"), 4),
		"commission_rate": flt(allocation.get("commission_rate"), 4),
		"commission_amount": flt(allocation.get("commission_amount"), 2),
	})


def append_total(data):
	if not data:
		return
	data.append({
		"invoice": _("Total"),
		"allocated_sales": flt(sum(row["allocated_sales"] for row in data), 2),
		"commission_amount": flt(sum(row["commission_amount"] for row in data), 2),
		"bold": 1,
	})

# Copyright (c) 2026, POS Next and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	from_date, to_date = validate_filters(filters)
	columns = get_columns()
	data = get_data(filters, from_date, to_date)
	append_total_row(data)
	return columns, data


def validate_filters(filters):
	from_date = getdate(filters.get("from_date") or nowdate())
	to_date = getdate(filters.get("to_date") or nowdate())
	if from_date > to_date:
		frappe.throw(_("From Date cannot be after To Date"))
	return from_date, to_date


def get_columns():
	return [
		{
			"label": _("Posting Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"label": _("POS Profile"),
			"fieldname": "pos_profile",
			"fieldtype": "Link",
			"options": "POS Profile",
			"width": 220,
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 220,
		},
		{
			"label": _("Invoices"),
			"fieldname": "invoice_count",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": _("Gross Sales"),
			"fieldname": "gross_sales",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Returns"),
			"fieldname": "returns_total",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Net Sales"),
			"fieldname": "net_sales",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Paid Amount"),
			"fieldname": "paid_amount",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Outstanding"),
			"fieldname": "outstanding_amount",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Discount"),
			"fieldname": "discount_amount",
			"fieldtype": "Currency",
			"width": 120,
		},
	]


def get_data(filters, from_date, to_date):
	conditions, params = get_invoice_conditions(filters, from_date, to_date)
	if filters.get("item_group"):
		return get_item_group_data(filters, conditions, params)
	return get_invoice_level_data(conditions, params)


def get_invoice_conditions(filters, from_date, to_date):
	conditions = [
		"si.docstatus = 1",
		"si.is_pos = 1",
		"si.posting_date BETWEEN %(from_date)s AND %(to_date)s",
	]
	params = {
		"from_date": from_date,
		"to_date": to_date,
	}

	if filters.get("pos_profile"):
		conditions.append("si.pos_profile = %(pos_profile)s")
		params["pos_profile"] = filters.get("pos_profile")

	return conditions, params


def get_invoice_level_data(conditions, params):
	rows = frappe.db.sql(
		f"""
		SELECT
			si.posting_date,
			si.pos_profile,
			si.company,
			COUNT(si.name) AS invoice_count,
			COALESCE(SUM(CASE WHEN si.is_return = 0 THEN si.grand_total ELSE 0 END), 0) AS gross_sales,
			COALESCE(SUM(CASE WHEN si.is_return = 1 THEN ABS(si.grand_total) ELSE 0 END), 0) AS returns_total,
			COALESCE(SUM(si.grand_total), 0) AS net_sales,
			COALESCE(SUM(si.paid_amount), 0) AS paid_amount,
			COALESCE(SUM(si.outstanding_amount), 0) AS outstanding_amount,
			COALESCE(SUM(si.discount_amount), 0) AS discount_amount
		FROM `tabSales Invoice` si
		WHERE {" AND ".join(conditions)}
			AND si.pos_profile IS NOT NULL
			AND si.pos_profile != ''
		GROUP BY si.posting_date, si.pos_profile, si.company
		ORDER BY si.posting_date ASC, si.pos_profile ASC
		""",
		params,
		as_dict=True,
	)

	return [normalize_row(row) for row in rows]


def get_item_group_data(filters, conditions, params):
	item_group = filters.get("item_group")
	item_group_bounds = frappe.db.get_value("Item Group", item_group, ["lft", "rgt"], as_dict=True)
	if not item_group_bounds:
		frappe.throw(_("Item Group {0} does not exist").format(item_group))

	params = dict(params)
	params.update(
		{
			"item_group_lft": item_group_bounds.lft,
			"item_group_rgt": item_group_bounds.rgt,
		}
	)

	rows = frappe.db.sql(
		f"""
		SELECT
			filtered.posting_date,
			filtered.pos_profile,
			filtered.company,
			COUNT(filtered.name) AS invoice_count,
			COALESCE(SUM(CASE WHEN filtered.is_return = 0 THEN filtered.item_amount ELSE 0 END), 0) AS gross_sales,
			COALESCE(SUM(CASE WHEN filtered.is_return = 1 THEN ABS(filtered.item_amount) ELSE 0 END), 0) AS returns_total,
			COALESCE(SUM(filtered.item_amount), 0) AS net_sales,
			COALESCE(SUM(filtered.paid_amount * filtered.item_ratio), 0) AS paid_amount,
			COALESCE(SUM(filtered.outstanding_amount * filtered.item_ratio), 0) AS outstanding_amount,
			COALESCE(SUM(filtered.item_discount_amount), 0) AS discount_amount
		FROM (
			SELECT
				si.name,
				si.posting_date,
				si.pos_profile,
				si.company,
				si.is_return,
				si.paid_amount,
				si.outstanding_amount,
				COALESCE(SUM(sii.amount), 0) AS item_amount,
				COALESCE(SUM(sii.discount_amount), 0) AS item_discount_amount,
				CASE
					WHEN ABS(si.net_total) > 0 THEN ABS(COALESCE(SUM(sii.amount), 0)) / ABS(si.net_total)
					ELSE 0
				END AS item_ratio
			FROM `tabSales Invoice` si
			INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
			INNER JOIN `tabItem Group` ig ON ig.name = sii.item_group
			WHERE {" AND ".join(conditions)}
				AND si.pos_profile IS NOT NULL
				AND si.pos_profile != ''
				AND ig.lft >= %(item_group_lft)s
				AND ig.rgt <= %(item_group_rgt)s
			GROUP BY si.name, si.posting_date, si.pos_profile, si.company, si.is_return,
				si.paid_amount, si.outstanding_amount, si.net_total
		) filtered
		GROUP BY filtered.posting_date, filtered.pos_profile, filtered.company
		ORDER BY filtered.posting_date ASC, filtered.pos_profile ASC
		""",
		params,
		as_dict=True,
	)

	return [normalize_row(row) for row in rows]


def normalize_row(row):
	return {
		"posting_date": row.posting_date,
		"pos_profile": row.pos_profile,
		"company": row.company,
		"invoice_count": cint(row.invoice_count),
		"gross_sales": flt(row.gross_sales, 2),
		"returns_total": flt(row.returns_total, 2),
		"net_sales": flt(row.net_sales, 2),
		"paid_amount": flt(row.paid_amount, 2),
		"outstanding_amount": flt(row.outstanding_amount, 2),
		"discount_amount": flt(row.discount_amount, 2),
	}


def append_total_row(data):
	if not data:
		return

	data.append(
		{
			"posting_date": None,
			"pos_profile": _("Total"),
			"company": "",
			"invoice_count": sum(cint(row.get("invoice_count")) for row in data),
			"gross_sales": flt(sum(flt(row.get("gross_sales")) for row in data), 2),
			"returns_total": flt(sum(flt(row.get("returns_total")) for row in data), 2),
			"net_sales": flt(sum(flt(row.get("net_sales")) for row in data), 2),
			"paid_amount": flt(sum(flt(row.get("paid_amount")) for row in data), 2),
			"outstanding_amount": flt(sum(flt(row.get("outstanding_amount")) for row in data), 2),
			"discount_amount": flt(sum(flt(row.get("discount_amount")) for row in data), 2),
			"bold": 1,
		}
	)

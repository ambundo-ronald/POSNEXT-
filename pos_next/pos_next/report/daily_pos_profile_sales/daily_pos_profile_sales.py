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

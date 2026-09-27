import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate


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
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 115},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 190},
		{"label": _("POS Profile"), "fieldname": "pos_profile", "fieldtype": "Link", "options": "POS Profile", "width": 170},
		{"label": _("Invoices"), "fieldname": "invoice_count", "fieldtype": "Int", "width": 90},
		{"label": _("Net Sales Before Commission"), "fieldname": "net_sales", "fieldtype": "Currency", "width": 190},
		{"label": _("Sales Person Commission"), "fieldname": "commission_amount", "fieldtype": "Currency", "width": 180},
		{"label": _("Business Earnings After Commission"), "fieldname": "business_earnings", "fieldtype": "Currency", "width": 210},
	]


def get_data(filters, from_date, to_date):
	conditions = [
		"si.docstatus = 1",
		"si.posting_date BETWEEN %(from_date)s AND %(to_date)s",
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
			sii.amount, sii.posa_sales_person, sii.posa_commission_amount,
			sii.posa_sales_person_allocations
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE {" AND ".join(conditions)}
		ORDER BY si.posting_date, si.pos_profile
		""",
		params,
		as_dict=True,
	)

	grouped = defaultdict(lambda: {"invoices": set(), "net_sales": 0, "commission_amount": 0})
	for row in rows:
		if filters.get("sales_person") and not has_sales_person(row, filters.sales_person):
			continue
		key = (row.posting_date, row.company, row.pos_profile)
		grouped[key]["invoices"].add(row.invoice)
		grouped[key]["net_sales"] += flt(row.amount)
		grouped[key]["commission_amount"] += flt(row.posa_commission_amount)

	return [{
		"posting_date": key[0],
		"company": key[1],
		"pos_profile": key[2],
		"invoice_count": len(values["invoices"]),
		"net_sales": flt(values["net_sales"], 2),
		"commission_amount": flt(values["commission_amount"], 2),
		"business_earnings": flt(values["net_sales"] - values["commission_amount"], 2),
	} for key, values in grouped.items()]


def has_sales_person(row, sales_person):
	if row.posa_sales_person == sales_person:
		return True
	if not row.posa_sales_person_allocations:
		return False
	try:
		allocations = json.loads(row.posa_sales_person_allocations)
	except (TypeError, ValueError):
		return False
	return any(allocation.get("sales_person") == sales_person for allocation in allocations or [])


def append_total(data):
	if not data:
		return
	data.append({
		"company": _("Total"),
		"invoice_count": sum(cint(row["invoice_count"]) for row in data),
		"net_sales": flt(sum(row["net_sales"] for row in data), 2),
		"commission_amount": flt(sum(row["commission_amount"] for row in data), 2),
		"business_earnings": flt(sum(row["business_earnings"] for row in data), 2),
		"bold": 1,
	})

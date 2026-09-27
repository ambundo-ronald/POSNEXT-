import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class POSCommissionSettings(Document):
	def validate(self):
		self._validate_commission_items()
		self._validate_accounts()

	def _validate_commission_items(self):
		seen = set()
		for row in self.get("commission_items") or []:
			rate = flt(row.sales_person_percentage, 4)
			if rate < 0 or rate > 100:
				frappe.throw(_("Sales Person % for item {0} must be between 0 and 100.").format(row.item_code))
			row.company_percentage = flt(100 - rate, 4)
			key = (row.company, row.item_code, row.warehouse or "")
			if key in seen:
				frappe.throw(_("Duplicate commission rule for company {0}, item {1}, warehouse {2}.").format(row.company, row.item_code, row.warehouse or _("All Warehouses")))
			seen.add(key)
			if row.warehouse:
				warehouse_company = frappe.db.get_value("Warehouse", row.warehouse, "company")
				if warehouse_company != row.company:
					frappe.throw(_("Warehouse {0} does not belong to company {1}.").format(row.warehouse, row.company))

	def _validate_accounts(self):
		seen = set()
		for row in self.get("commission_accounts") or []:
			if row.company in seen:
				frappe.throw(_("Only one accounting row is allowed for company {0}.").format(row.company))
			seen.add(row.company)
			for fieldname in ("commission_expense_account", "commission_payable_account"):
				account = row.get(fieldname)
				account_data = frappe.db.get_value("Account", account, ["company", "is_group"], as_dict=True)
				if not account_data or account_data.company != row.company or account_data.is_group:
					frappe.throw(_("Account {0} must be a ledger account belonging to {1}.").format(account, row.company))


@frappe.whitelist()
def fetch_commission_items(company, warehouse=None, item_group=None):
	if not {"System Manager", "Sales Manager"}.intersection(frappe.get_roles()):
		frappe.throw(_("You are not permitted to manage commission settings."), frappe.PermissionError)
	if not company:
		frappe.throw(_("Company is required."))

	filters = {"disabled": 0, "is_sales_item": 1}

	if item_group:
		bounds = frappe.db.get_value("Item Group", item_group, ["lft", "rgt"], as_dict=True)
		if not bounds:
			frappe.throw(_("Item Group {0} does not exist.").format(item_group))
		groups = frappe.get_all("Item Group", filters={"lft": [">=", bounds.lft], "rgt": ["<=", bounds.rgt]}, pluck="name")
		filters["item_group"] = ["in", groups]

	items = frappe.get_all("Item", filters=filters, fields=["name as item_code", "item_name", "item_group", "is_stock_item", "custom_company"], order_by="item_name", limit_page_length=0)
	items = [item for item in items if item.custom_company in (None, "", company)]

	if warehouse:
		warehouse_company = frappe.db.get_value("Warehouse", warehouse, "company")
		if warehouse_company != company:
			frappe.throw(_("Warehouse {0} does not belong to company {1}.").format(warehouse, company))
		available_codes = set(frappe.get_all("Bin", filters={"warehouse": warehouse, "actual_qty": ["!=", 0]}, pluck="item_code", limit_page_length=0))
		items = [
			item for item in items
			if not item.is_stock_item or item.item_code in available_codes
		]

	existing = get_commission_rate_map([item.item_code for item in items], company, warehouse=warehouse)
	return [{
		"company": company,
		"item_code": item.item_code,
		"item_name": item.item_name,
		"item_group": item.item_group,
		"warehouse": warehouse or "",
		"sales_person_percentage": flt(existing.get(item.item_code, {}).get("sales_person_percentage"), 4),
		"company_percentage": flt(existing.get(item.item_code, {}).get("company_percentage", 100), 4),
	} for item in items]


def get_commission_rate(item_code, company, warehouse=None):
	return get_commission_rate_map([item_code], company, warehouse).get(item_code)


def get_commission_rate_map(item_codes, company, warehouse=None):
	if not item_codes or not company or not frappe.db.table_exists("POS Commission Item"):
		return {}

	rows = frappe.db.sql(
		"""
		SELECT item_code, warehouse, sales_person_percentage, company_percentage
		FROM `tabPOS Commission Item`
		WHERE parent = 'POS Commission Settings'
			AND parenttype = 'POS Commission Settings'
			AND company = %(company)s
			AND item_code IN %(item_codes)s
			AND (IFNULL(warehouse, '') = '' OR warehouse = %(warehouse)s)
		ORDER BY CASE WHEN warehouse = %(warehouse)s AND %(warehouse)s != '' THEN 0 ELSE 1 END, idx
		""",
		{"company": company, "item_codes": tuple(set(item_codes)), "warehouse": warehouse or ""},
		as_dict=True,
	)

	result = {}
	for row in rows:
		if row.item_code not in result:
			result[row.item_code] = {
				"sales_person_percentage": flt(row.sales_person_percentage, 4),
				"company_percentage": flt(row.company_percentage, 4),
				"warehouse": row.warehouse or "",
			}
	return result


def get_commission_accounts(company):
	if not company or not frappe.db.table_exists("POS Commission Account"):
		return {}
	return frappe.db.get_value(
		"POS Commission Account",
		{"parent": "POS Commission Settings", "company": company},
		["commission_expense_account", "commission_payable_account"],
		as_dict=True,
	) or {}

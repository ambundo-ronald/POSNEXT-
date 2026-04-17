import frappe


def execute():
	if not frappe.db.exists("DocType", "BrainWise Branding"):
		return

	try:
		doc = frappe.get_single("BrainWise Branding")
	except Exception:
		return

	updates = {}

	if doc.brand_text in (None, "", "Powered by"):
		updates["brand_text"] = "Powered by"

	if doc.brand_name == "BrainWise":
		updates["brand_name"] = "Jorovin Ltd"

	if updates:
		for fieldname, value in updates.items():
			frappe.db.set_value("BrainWise Branding", doc.name, fieldname, value, update_modified=False)

		frappe.db.commit()

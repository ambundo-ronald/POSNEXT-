import frappe


def execute():
	if not frappe.db.table_exists("SMS Enabler Payment Register"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabSMS Enabler Payment Register`
		SET allocated_amount = amount
		WHERE status = 'Consumed'
			AND IFNULL(allocated_amount, 0) = 0
		"""
	)
	frappe.db.sql(
		"""
		UPDATE `tabSMS Enabler Payment Register`
		SET available_amount = GREATEST(
			IFNULL(amount, 0) - IFNULL(allocated_amount, 0),
			0
		)
		WHERE status IN ('Pending', 'Matched', 'Partially Allocated', 'Consumed')
		"""
	)

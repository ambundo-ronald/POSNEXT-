# -*- coding: utf-8 -*-
# Copyright (c) 2026, BrainWise and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class SMSEnablerPaymentRegister(Document):
	def validate(self):
		if not self.received_at:
			self.received_at = now_datetime()

		if not self.status:
			self.status = "Pending"

		self.amount = flt(self.amount)

		if self.transaction_id:
			existing = self.get_existing_payment_with_same_reference()
			if existing and self.status != "Duplicate":
				self.status = "Duplicate"
			elif (
				not existing
				and self.status == "Duplicate"
				and self.parse_status == "Parsed"
			):
				self.status = "Pending"

	def get_existing_payment_with_same_reference(self):
		"""Return an earlier live SMS payment with the same bank reference.

		Bank references are only meaningful inside the bank/source context. The
		old check used transaction_id globally, so an old duplicate row or a row
		from another source/company could keep marking valid payments duplicate.
		"""
		conditions = [
			"name != %(name)s",
			"transaction_id = %(transaction_id)s",
			"status NOT IN ('Duplicate', 'Failed Parse')",
		]
		params = {
			"name": self.name,
			"transaction_id": self.transaction_id,
		}

		for fieldname in ("sender", "source", "company"):
			value = self.get(fieldname)
			if value:
				conditions.append(f"`{fieldname}` = %({fieldname})s")
				params[fieldname] = value

		if self.amount:
			conditions.append("ABS(amount - %(amount)s) < 0.01")
			params["amount"] = self.amount

		result = frappe.db.sql(
			f"""
			SELECT name
			FROM `tabSMS Enabler Payment Register`
			WHERE {" AND ".join(conditions)}
			ORDER BY creation ASC
			LIMIT 1
			""",
			params,
			as_dict=True,
		)
		return result[0].name if result else None

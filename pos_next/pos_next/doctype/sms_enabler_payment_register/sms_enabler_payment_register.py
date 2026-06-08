# -*- coding: utf-8 -*-
# Copyright (c) 2026, BrainWise and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class SMSEnablerPaymentRegister(Document):
	def validate(self):
		if not self.received_at:
			self.received_at = now_datetime()

		if not self.status:
			self.status = "Pending"

		self.validate_pos_profile_company()

		self.amount = flt(self.amount)
		self.allocated_amount = max(flt(self.allocated_amount), 0)
		self.available_amount = max(flt(self.amount) - self.allocated_amount, 0)

		if self.status in ("Pending", "Matched", "Partially Allocated", "Consumed"):
			if self.available_amount <= 0.01:
				self.status = "Consumed"
			elif self.allocated_amount > 0:
				self.status = "Partially Allocated"
			elif self.status in ("Partially Allocated", "Consumed"):
				self.status = "Pending"

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

	def validate_pos_profile_company(self):
		if not self.pos_profile:
			return

		profile_company = frappe.db.get_value("POS Profile", self.pos_profile, "company")
		if self.company and profile_company != self.company:
			frappe.throw(
				_("POS Profile {0} belongs to company {1}, not {2}.").format(
					self.pos_profile,
					profile_company,
					self.company,
				)
			)
		if not self.company:
			self.company = profile_company

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

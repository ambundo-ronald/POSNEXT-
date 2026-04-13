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
			existing = frappe.db.exists(
				"SMS Enabler Payment Register",
				{"transaction_id": self.transaction_id, "name": ["!=", self.name]},
			)
			if existing and self.status != "Duplicate":
				self.status = "Duplicate"

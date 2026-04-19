# Copyright (c) 2026, POS Next and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint


class POSNextGlobalSettings(Document):
	def validate(self):
		if cint(self.get("sms_enabler_enabled")):
			if not self.get("sms_enabler_token"):
				self.sms_enabler_token = frappe.generate_hash(length=32)
			if not self.get("sms_enabler_source"):
				self.sms_enabler_source = "SMS Enabler"

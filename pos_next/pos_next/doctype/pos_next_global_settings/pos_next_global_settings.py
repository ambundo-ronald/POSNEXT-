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

		seen = set()
		for row in self.get("sms_enabler_sender_mappings") or []:
			row.match_text = (row.get("match_text") or "").strip()
			if not row.match_text:
				frappe.throw("SMS sender mapping match text is required")
			key = row.match_text.lower()
			if key in seen:
				frappe.throw(f"Duplicate SMS sender mapping: {row.match_text}")
			seen.add(key)

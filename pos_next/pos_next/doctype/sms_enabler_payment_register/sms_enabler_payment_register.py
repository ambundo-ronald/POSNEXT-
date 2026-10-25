# -*- coding: utf-8 -*-
# Copyright (c) 2026, BrainWise and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime, nowdate


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


@frappe.whitelist()
def consume_as_non_sales_receipt(name, reason, credit_account, posting_date=None, remarks=None):
	if not set(frappe.get_roles()) & {"System Manager", "Sales Manager"}:
		frappe.throw(
			_("Only a System Manager or Sales Manager can allocate non-sales receipts."),
			frappe.PermissionError,
		)

	payment = frappe.get_doc("SMS Enabler Payment Register", name)
	if payment.status not in ("Pending", "Matched", "Partially Allocated"):
		frappe.throw(_("SMS payment {0} is already {1}.").format(payment.name, payment.status))
	if payment.non_sales_journal_entry:
		frappe.throw(
			_("SMS payment {0} is already linked to Journal Entry {1}.").format(
				payment.name, payment.non_sales_journal_entry
			)
		)

	reason = (reason or "").strip()
	allowed_reasons = {
		"Director Injection",
		"Shareholder Loan",
		"Capital Contribution",
		"Bank Transfer / Internal Transfer",
		"Historical Offline Sale - Stock Already Reconciled",
		"Other Non-Sales Receipt",
	}
	if reason not in allowed_reasons:
		frappe.throw(_("Select a valid non-sales receipt reason."))

	company = payment.company
	if not company and payment.pos_profile:
		company = frappe.db.get_value("POS Profile", payment.pos_profile, "company")
	if not company:
		frappe.throw(_("Set the company on SMS payment {0} before allocating it.").format(name))

	account = frappe.db.get_value(
		"Account",
		credit_account,
		["name", "company", "is_group", "account_currency", "account_type", "root_type"],
		as_dict=True,
	)
	if not account or account.company != company or account.is_group:
		frappe.throw(_("Credit account must be a ledger account for company {0}.").format(company))
	if account.account_type in ("Receivable", "Payable"):
		frappe.throw(_("Receivable and Payable accounts cannot be used for this allocation."))
	if account.root_type not in ("Liability", "Equity", "Asset"):
		frappe.throw(_("Use a Liability, Equity, Cash, or Bank account for non-sales receipts."))
	if account.root_type == "Asset" and account.account_type not in ("Cash", "Bank"):
		frappe.throw(_("Only Cash or Bank asset accounts can be used for internal transfers."))
	if (
		reason == "Historical Offline Sale - Stock Already Reconciled"
		and account.root_type != "Liability"
	):
		frappe.throw(
			_("Historical offline sales must be posted to a Liability clearing account for later accounting review.")
		)

	company_currency = frappe.get_cached_value("Company", company, "default_currency")
	payment_currency = payment.currency or company_currency
	if payment_currency != company_currency or account.account_currency != company_currency:
		frappe.throw(
			_("Non-sales SMS allocation currently requires company-currency accounts ({0}).").format(
				company_currency
			)
		)

	amount = max(flt(payment.amount) - flt(payment.allocated_amount), 0)
	if amount <= 0.01:
		frappe.throw(_("SMS payment {0} has no available amount to allocate.").format(name))
	from pos_next.api.smsenabler_mpesa import (
		_get_phone_mop_for_company,
		_resolve_mapped_mode_of_payment,
	)

	# Older SMS payments may predate sender mappings; resolve the same way as
	# invoice allocation does.
	mode_of_payment = (
		payment.mode_of_payment
		or _resolve_mapped_mode_of_payment(
			sender=payment.sender, source=payment.source, message=payment.raw_message
		)
		or _get_phone_mop_for_company(company)
	)
	if not mode_of_payment:
		frappe.throw(
			_(
				"Set the Mode of Payment on SMS payment {0}, or configure an enabled Phone Mode of Payment for company {1}."
			).format(name, company)
		)

	from pos_next.api.partial_payments import _resolve_payment_account

	bank_account = _resolve_payment_account(mode_of_payment, company)
	if bank_account == account.name:
		frappe.throw(_("The debit and credit accounts must be different."))
	bank_currency = frappe.db.get_value("Account", bank_account, "account_currency")
	if bank_currency != company_currency:
		frappe.throw(
			_("The Mode of Payment account must use company currency {0}.").format(
				company_currency
			)
		)

	journal_entry = frappe.new_doc("Journal Entry")
	journal_entry.voucher_type = "Journal Entry"
	journal_entry.company = company
	journal_entry.posting_date = getdate(posting_date or payment.received_at or nowdate())
	journal_entry.cheque_no = (payment.transaction_id or payment.name)[:140]
	journal_entry.cheque_date = journal_entry.posting_date
	journal_entry.user_remark = _("{0} from SMS Enabler payment {1}. {2}").format(
		reason,
		payment.name,
		(remarks or "").strip(),
	).strip()
	journal_entry.append(
		"accounts",
		{
			"account": bank_account,
			"debit_in_account_currency": amount,
			"credit_in_account_currency": 0,
		},
	)
	journal_entry.append(
		"accounts",
		{
			"account": account.name,
			"debit_in_account_currency": 0,
			"credit_in_account_currency": amount,
		},
	)
	journal_entry.flags.ignore_permissions = True
	journal_entry.insert()
	journal_entry.submit()

	payment.company = company
	payment.mode_of_payment = mode_of_payment
	payment.allocated_amount = flt(payment.allocated_amount) + amount
	payment.available_amount = 0
	payment.status = "Consumed - Non-Sales"
	payment.non_sales_reason = reason
	payment.non_sales_credit_account = account.name
	payment.non_sales_amount = amount
	payment.non_sales_journal_entry = journal_entry.name
	payment.non_sales_remarks = (remarks or "").strip()
	payment.non_sales_processed_by = frappe.session.user
	payment.non_sales_processed_at = now_datetime()
	payment.flags.ignore_permissions = True
	payment.save()

	return {
		"success": True,
		"journal_entry": journal_entry.name,
		"amount": amount,
		"status": payment.status,
	}

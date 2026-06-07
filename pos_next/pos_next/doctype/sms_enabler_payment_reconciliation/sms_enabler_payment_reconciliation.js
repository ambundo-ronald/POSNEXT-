// Copyright (c) 2026, BrainWise and contributors
// For license information, please see license.txt

frappe.ui.form.on("SMS Enabler Payment Reconciliation", {
	onload(frm) {
		if (frm.fields_dict.company && !frm.doc.company) {
			frm.set_value("company", frappe.defaults.get_user_default("Company"));
		}
	},

	company(frm) {
		if (frm.doc.pos_profile) {
			frm.set_value("pos_profile", "");
		}
	},

	refresh(frm) {
		frm.disable_save();
		frm.set_df_property("invoices", "cannot_add_rows", true);
		frm.set_df_property("invoices", "cannot_delete_rows", true);
		frm.set_df_property("sms_payments", "cannot_add_rows", true);
		frm.set_df_property("sms_payments", "cannot_delete_rows", true);

		frm.add_custom_button(__("Get Unreconciled Entries"), () => {
			frm.trigger("fetch_entries");
		});
		toggle_allocate_button(frm);
	},

	onload_post_render(frm) {
		frm.set_query("pos_profile", () => ({
			filters: {
				company: frm.doc.company,
			},
		}));
		frm.set_query("invoice_name", () => ({
			filters: {
				docstatus: 1,
				outstanding_amount: [">", 0],
				company: frm.doc.company,
				pos_profile: frm.doc.pos_profile,
				customer: frm.doc.customer,
			},
		}));
	},

	fetch_entries(frm) {
		frm.trigger("refresh_reconciliation_entries");
	},

	refresh_reconciliation_entries(frm) {
		frm.clear_table("invoices");
		frm.clear_table("sms_payments");

		frappe.call({
			method:
				"pos_next.pos_next.doctype.sms_enabler_payment_reconciliation.sms_enabler_payment_reconciliation.get_outstanding_invoices",
			args: {
				company: frm.doc.company || "",
				pos_profile: frm.doc.pos_profile || "",
				customer: frm.doc.customer || "",
				invoice_name: frm.doc.invoice_name || "",
				from_date: frm.doc.from_invoice_date || "",
				to_date: frm.doc.to_invoice_date || "",
			},
			callback(response) {
				const invoices = response.message || [];
				frm.clear_table("invoices");
				for (const invoice of invoices) {
					const row = frm.add_child("invoices");
					row.sales_invoice = invoice.sales_invoice;
					row.posting_date = invoice.posting_date;
					row.customer = invoice.customer;
					row.grand_total = invoice.grand_total;
					row.outstanding_amount = invoice.outstanding_amount;
					row.currency = invoice.currency;
				}
				frm.refresh_field("invoices");
				toggle_allocate_button(frm);
			},
		});

		frappe.call({
			method:
				"pos_next.pos_next.doctype.sms_enabler_payment_reconciliation.sms_enabler_payment_reconciliation.get_unreconciled_sms_payments",
			args: {
				company: frm.doc.company || "",
				pos_profile: frm.doc.pos_profile || "",
				search: frm.doc.sms_search || "",
				from_date: frm.doc.from_sms_payment_date || "",
				to_date: frm.doc.to_sms_payment_date || "",
			},
			callback(response) {
				const payments = response.message || [];
				frm.clear_table("sms_payments");
				for (const payment of payments) {
					const row = frm.add_child("sms_payments");
					row.sms_payment = payment.sms_payment;
					row.received_at = payment.received_at;
					row.payer_name = payment.payer_name || payment.source;
					row.payer_phone = payment.payer_phone || payment.sender;
					row.transaction_id = payment.transaction_id;
					row.amount = payment.amount;
					row.mode_of_payment = payment.mode_of_payment;
				}
				frm.refresh_field("sms_payments");
				toggle_allocate_button(frm);

				if (!frm.doc.invoices.length && !frm.doc.sms_payments.length) {
					frappe.msgprint({
						title: __("No Entries Found"),
						message: __(
							"No outstanding invoices or unreconciled SMS payments found for the selected filters.",
						),
						indicator: "orange",
					});
				}
			},
		});
	},

	process_payments(frm) {
		const selected = frm.get_selected();
		const invoice_rows = selected.invoices || [];
		const payment_rows = selected.sms_payments || [];

		if (!invoice_rows.length || !payment_rows.length) {
			frappe.msgprint({
				title: __("No Entries Selected"),
				message: __("Please select at least one invoice and one SMS payment."),
				indicator: "orange",
			});
			return;
		}

		const invoice_names = frm.doc.invoices
			.filter((invoice) => invoice_rows.includes(invoice.name))
			.map((invoice) => invoice.sales_invoice);
		const sms_payment_names = frm.doc.sms_payments
			.filter((payment) => payment_rows.includes(payment.name))
			.map((payment) => payment.sms_payment);

		frappe.dom.freeze(__("Processing SMS Enabler Reconciliation..."));
		frm.custom_buttons?.Allocate?.prop("disabled", true);

		frappe.call({
			method:
				"pos_next.pos_next.doctype.sms_enabler_payment_reconciliation.sms_enabler_payment_reconciliation.process_sms_enabler_reconciliation",
			args: {
				invoice_names,
				sms_payment_names,
			},
			callback(response) {
				if (response.exc) {
					frappe.show_alert(
						{
							message: __("Reconciliation failed. Check Error Log."),
							indicator: "red",
						},
						8,
					);
					return;
				}
				const count = response.message?.payment_entries?.length || 0;
				frappe.show_alert(
					{
						message: __("{0} payment entry(s) created and reconciled.", [
							count,
						]),
						indicator: "green",
					},
					5,
				);
				frm.trigger("refresh_reconciliation_entries");
			},
			always() {
				frappe.dom.unfreeze();
				frm.custom_buttons?.Allocate?.prop("disabled", false);
			},
		});
	},
});

function toggle_allocate_button(frm) {
	frm.remove_custom_button(__("Allocate"));
	if (frm.doc.invoices?.length && frm.doc.sms_payments?.length) {
		const button = frm.add_custom_button(__("Allocate"), () => {
			frm.trigger("process_payments");
		});
		button.addClass("btn-primary");
	}
}

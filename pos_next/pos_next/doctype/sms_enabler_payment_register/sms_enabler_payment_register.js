frappe.ui.form.on("SMS Enabler Payment Register", {
	refresh(frm) {
		const can_assign_profile =
			frm.doc.status === "Pending" &&
			!frm.doc.pos_profile &&
			!frm.doc.payment_entry

		frm.set_df_property("pos_profile", "read_only", !can_assign_profile)
		frm.set_query("pos_profile", () => ({
			filters: frm.doc.company ? { company: frm.doc.company } : {},
		}))

		const can_allocate_non_sales =
			!frm.is_new() &&
			["Pending", "Matched", "Partially Allocated"].includes(frm.doc.status) &&
			!frm.doc.non_sales_journal_entry &&
			(frappe.user.has_role("System Manager") || frappe.user.has_role("Sales Manager"))

		if (can_allocate_non_sales) {
			frm.add_custom_button(__("Mark as Non-Sales Receipt"), () => {
				show_non_sales_dialog(frm)
			}, __("Actions"))
		}

		if (frm.is_new() || ["Consumed", "Consumed - Non-Sales"].includes(frm.doc.status) || frm.doc.payment_entry) {
			return
		}

		frm.add_custom_button(__("Reparse SMS"), () => {
			frappe.call({
				method: "pos_next.api.smsenabler_mpesa.reparse_sms_payment",
				args: {
					name: frm.doc.name,
				},
				freeze: true,
				freeze_message: __("Reparsing SMS..."),
				callback(response) {
					const result = response.message || {}
					if (result.success) {
						frappe.show_alert({
							message: __("SMS reparsed successfully"),
							indicator: "green",
						})
						frm.reload_doc()
					}
				},
			})
		})
	},
})

function show_non_sales_dialog(frm) {
	const available_amount = Math.max(
		flt(frm.doc.amount) - flt(frm.doc.allocated_amount),
		0,
	)
	const dialog = new frappe.ui.Dialog({
		title: __("Mark as Non-Sales Receipt"),
		fields: [
			{
				fieldtype: "Currency",
				fieldname: "amount",
				label: __("Available Amount"),
				default: available_amount,
				read_only: 1,
			},
			{
				fieldtype: "Select",
				fieldname: "reason",
				label: __("Reason"),
				options: [
					"Director Injection",
					"Shareholder Loan",
					"Capital Contribution",
					"Bank Transfer / Internal Transfer",
					"Historical Offline Sale - Stock Already Reconciled",
					"Other Non-Sales Receipt",
				],
				reqd: 1,
			},
			{
				fieldtype: "Link",
				fieldname: "credit_account",
				label: __("Credit Account"),
				options: "Account",
				reqd: 1,
				get_query: () => ({
					filters: {
						company: frm.doc.company,
						is_group: 0,
						root_type: ["in", ["Liability", "Equity", "Asset"]],
					},
				}),
			},
			{
				fieldtype: "Date",
				fieldname: "posting_date",
				label: __("Posting Date"),
				default: frappe.datetime.get_today(),
				reqd: 1,
			},
			{
				fieldtype: "Small Text",
				fieldname: "remarks",
				label: __("Remarks"),
			},
		],
		primary_action_label: __("Create Journal Entry"),
		primary_action(values) {
			frappe.confirm(
				__("Post {0} as a non-sales receipt? This cannot be matched to an invoice afterward.", [
					format_currency(available_amount, frm.doc.currency),
				]),
				() => {
					dialog.get_primary_btn().prop("disabled", true)
					frappe.call({
						method: "pos_next.pos_next.doctype.sms_enabler_payment_register.sms_enabler_payment_register.consume_as_non_sales_receipt",
						args: {
							name: frm.doc.name,
							reason: values.reason,
							credit_account: values.credit_account,
							posting_date: values.posting_date,
							remarks: values.remarks,
						},
						freeze: true,
						freeze_message: __("Posting non-sales receipt..."),
						callback(response) {
							if (!response.exc && response.message?.journal_entry) {
								dialog.hide()
								frappe.show_alert({
									message: __("Journal Entry {0} created", [response.message.journal_entry]),
									indicator: "green",
								})
								frm.reload_doc()
							}
						},
						always() {
							dialog.get_primary_btn().prop("disabled", false)
						},
					})
				},
			)
		},
	})
	dialog.show()
}

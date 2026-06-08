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

		if (frm.is_new() || frm.doc.status === "Consumed" || frm.doc.payment_entry) {
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

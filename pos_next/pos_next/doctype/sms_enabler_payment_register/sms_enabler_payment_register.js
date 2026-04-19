frappe.ui.form.on("SMS Enabler Payment Register", {
	refresh(frm) {
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

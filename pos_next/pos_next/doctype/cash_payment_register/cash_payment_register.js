frappe.ui.form.on("Cash Payment Register", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.status === "Reconciled" || !frm.doc.sales_invoice) {
			return;
		}

		frm.add_custom_button(__("Retry Payment Entry"), async () => {
			frappe.dom.freeze(__("Creating Payment Entry from cash register..."));

			try {
				const { message } = await frappe.call({
					method: "pos_next.pos_next.doctype.cash_payment_register.cash_payment_register.retry_cash_payment_entry",
					args: {
						name: frm.doc.name,
					},
				});

				frappe.show_alert({
					message: __("Cash payment reconciled with Payment Entry {0}", [message?.payment_entry || ""]),
					indicator: "green",
				});
				await frm.reload_doc();
			} finally {
				frappe.dom.unfreeze();
			}
		}).addClass("btn-primary");
	},
});


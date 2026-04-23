frappe.ui.form.on("SMS Enabler Payment Entry Sync", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.status === "Running") {
			return;
		}

		frm.add_custom_button(__("Run Sync"), async () => {
			await frm.save();
			frappe.dom.freeze(__("Syncing linked SMS Enabler payments..."));

			try {
				const { message } = await frappe.call({
					method: "pos_next.pos_next.doctype.sms_enabler_payment_entry_sync.sms_enabler_payment_entry_sync.run_sync",
					args: {
						docname: frm.doc.name,
					},
				});

				const created = message?.created_payment_entries || 0;
				const linked = message?.linked_existing_count || 0;

				frappe.show_alert({
					message: __("SMS sync completed. Created: {0}, linked existing: {1}", [created, linked]),
					indicator: "green",
				});
				await frm.reload_doc();
			} finally {
				frappe.dom.unfreeze();
			}
		}).addClass("btn-primary");
	},
});

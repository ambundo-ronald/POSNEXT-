frappe.ui.form.on("POS Commission Settings", {
	setup(frm) {
		frm.set_query("warehouse", () => ({
			filters: { company: frm.doc.company, is_group: 0 },
		}));
	},

	refresh(frm) {
		frm.set_query("commission_expense_account", "commission_accounts", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return {
				filters: {
					company: row.company,
					is_group: 0,
					root_type: "Expense",
				},
			};
		});
		frm.set_query("commission_payable_account", "commission_accounts", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return {
				filters: {
					company: row.company,
					is_group: 0,
					root_type: "Liability",
				},
			};
		});
	},

	company(frm) {
		if (frm.doc.warehouse) {
			frm.set_value("warehouse", "");
		}
	},

	fetch_items(frm) {
		if (!frm.doc.company) {
			frappe.msgprint(__("Select a company before fetching items."));
			return;
		}

		frappe.call({
			method: "pos_next.pos_next.doctype.pos_commission_settings.pos_commission_settings.fetch_commission_items",
			args: {
				company: frm.doc.company,
				warehouse: frm.doc.warehouse,
				item_group: frm.doc.item_group,
			},
			freeze: true,
			freeze_message: __("Fetching commission items..."),
			callback(response) {
				const rows = response.message || [];
				const existing = new Map(
					(frm.doc.commission_items || []).map((row) => [
						[row.company, row.item_code, row.warehouse || ""].join("|"),
						row,
					]),
				);

				let added = 0;
				for (const item of rows) {
					const key = [item.company, item.item_code, item.warehouse || ""].join("|");
					if (existing.has(key)) {
						continue;
					}
					const row = frm.add_child("commission_items", item);
					row.company_percentage = 100 - (row.sales_person_percentage || 0);
					added += 1;
				}
				frm.refresh_field("commission_items");
				frappe.show_alert({
					message: __("{0} items added. {1} existing rules kept.", [added, rows.length - added]),
					indicator: "green",
				});
			},
		});
	},
});

frappe.ui.form.on("POS Commission Item", {
	sales_person_percentage(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const rate = Math.max(0, Math.min(100, flt(row.sales_person_percentage)));
		frappe.model.set_value(cdt, cdn, "sales_person_percentage", rate);
		frappe.model.set_value(cdt, cdn, "company_percentage", 100 - rate);
	},
});

frappe.provide("pos_next.payment_reconciliation");

(() => {
	const PAYMENT_SOURCE_SMS = "SMS Enabler";
	const RECONCILE_BUTTON_LABEL = __("Reconcile Selected SMS");

	function is_sms_source(frm) {
		return frm.doc.posa_payment_source === PAYMENT_SOURCE_SMS;
	}

	function get_selected_rows(frm, fieldname) {
		return frm.fields_dict[fieldname]?.grid?.get_selected_children?.() || [];
	}

	function get_selected_sms_payments(frm) {
		return get_selected_rows(frm, "payments").filter((row) => row.posa_sms_payment);
	}

	function clear_tables(frm) {
		frm.clear_table("invoices");
		frm.clear_table("payments");
		frm.clear_table("allocation");
		frm.refresh_fields(["invoices", "payments", "allocation"]);
	}

	function remove_standard_buttons(frm) {
		frm.remove_custom_button(__("Allocate"));
		frm.remove_custom_button(__("Reconcile"));
		frm.remove_custom_button(RECONCILE_BUTTON_LABEL);
	}

	function apply_sms_payments(frm, payments) {
		frm.clear_table("payments");

		(payments || []).forEach((payment) => {
			const row = frm.add_child("payments");
			row.reference_name = payment.reference_name;
			row.posting_date = payment.posting_date;
			row.amount = payment.amount;
			row.posa_reference_type = payment.reference_type;
			row.posa_sms_payment = payment.sms_payment;
		});

		frm.refresh_field("payments");
	}

	async function load_sms_payments(frm) {
		const response = await frappe.call({
			method: "pos_next.api.smsenabler_mpesa.get_sms_payments_for_payment_reconciliation",
			args: {
				company: frm.doc.company,
				party_type: frm.doc.party_type,
				party: frm.doc.party,
				search: frm.doc.payment_name,
			},
		});

		const payments = response.message?.payments || [];
		apply_sms_payments(frm, payments);
		return payments;
	}

	async function get_sms_unreconciled_entries(frm) {
		frm.clear_table("allocation");
		frm.refresh_field("allocation");

		if (frm.doc.party_type && frm.doc.party_type !== "Customer") {
			clear_tables(frm);
			frappe.throw(__("SMS Enabler reconciliation is only available for Customers."));
		}

		await frm.call({
			doc: frm.doc,
			method: "get_unreconciled_entries",
		});

		if (!frm.doc.invoices.length) {
			clear_tables(frm);
			frappe.throw(__("No Outstanding Invoices found for this party"));
		}

		const payments = await load_sms_payments(frm);
		if (!payments.length) {
			frappe.throw(__("No pending SMS Enabler payments found for this party"));
		}

		frm.refresh();
	}

	async function reconcile_selected_sms(frm) {
		if (frm.__posa_sms_reconciling) {
			return;
		}

		const invoices = get_selected_rows(frm, "invoices");
		const payments = get_selected_sms_payments(frm);

		if (invoices.length !== 1) {
			frappe.throw(__("Select exactly one invoice to reconcile."));
		}

		if (!payments.length) {
			frappe.throw(__("Select at least one SMS payment to reconcile."));
		}

		const invoice = invoices[0].invoice_number;
		const sms_payments = payments.map((payment) => payment.posa_sms_payment);

		frm.__posa_sms_reconciling = true;
		try {
			await frappe.call({
				method: "pos_next.api.smsenabler_mpesa.reconcile_invoice_with_sms_payments",
				args: {
					invoice,
					sms_payments,
				},
				freeze: true,
				freeze_message: __("Reconciling SMS payment..."),
			});

			frappe.show_alert({
				message: __("SMS payment reconciled successfully."),
				indicator: "green",
			});

			await get_sms_unreconciled_entries(frm);
		} finally {
			frm.__posa_sms_reconciling = false;
		}
	}

	function maybe_auto_reconcile(frm) {
		if (!is_sms_source(frm) || frm.__posa_sms_reconciling || frm.__posa_sms_auto_running) {
			return;
		}

		const invoices = get_selected_rows(frm, "invoices");
		const payments = get_selected_sms_payments(frm);

		if (invoices.length === 1 && payments.length === 1) {
			frm.__posa_sms_auto_running = true;
			reconcile_selected_sms(frm).finally(() => {
				frm.__posa_sms_auto_running = false;
			});
		}
	}

	function bind_grid_clicks(frm, fieldname) {
		const grid = frm.fields_dict[fieldname]?.grid;
		if (!grid) {
			return;
		}

		const $wrapper = $(grid.wrapper);
		$wrapper.off(".posaSms");

		$wrapper.on("change.posaSms", "input[type='checkbox']", () => {
			setTimeout(() => maybe_auto_reconcile(frm), 0);
		});

		$wrapper.on("click.posaSms", ".grid-row", (event) => {
			if (!is_sms_source(frm)) {
				return;
			}

			const $target = $(event.target);
			if (
				$target.closest("a, button, input, textarea, select, .btn-open-row, .grid-static-col").length
			) {
				return;
			}

			const $checkbox = $(event.currentTarget).find("input[type='checkbox']").first();
			if ($checkbox.length) {
				$checkbox.trigger("click");
				event.preventDefault();
				event.stopPropagation();
			}
		});
	}

	function apply_refresh(frm) {
		if (!is_sms_source(frm)) {
			frm.remove_custom_button(RECONCILE_BUTTON_LABEL);
			return;
		}

		remove_standard_buttons(frm);

		if (frm.doc.invoices.length && frm.doc.payments.length) {
			frm.add_custom_button(RECONCILE_BUTTON_LABEL, () => reconcile_selected_sms(frm));
			frm.change_custom_button_type(RECONCILE_BUTTON_LABEL, null, "primary");
			frm.change_custom_button_type(__("Get Unreconciled Entries"), null, "default");
		}

		bind_grid_clicks(frm, "invoices");
		bind_grid_clicks(frm, "payments");
	}

	function on_payment_source_change(frm) {
		clear_tables(frm);
		remove_standard_buttons(frm);
		frm.refresh();

		if (is_sms_source(frm) && frm.doc.receivable_payable_account) {
			frm.trigger("get_unreconciled_entries");
		}
	}

	pos_next.payment_reconciliation = {
		apply_refresh,
		get_sms_unreconciled_entries,
		reconcile_selected_sms,
		on_payment_source_change,
	};

	const Controller = erpnext?.accounts?.PaymentReconciliationController;
	if (!Controller || Controller.__posa_sms_patched) {
		return;
	}

	const original_get_unreconciled_entries = Controller.prototype.get_unreconciled_entries;
	Controller.prototype.get_unreconciled_entries = function () {
		if (is_sms_source(this.frm)) {
			return get_sms_unreconciled_entries(this.frm);
		}

		return original_get_unreconciled_entries.call(this);
	};

	const original_refresh = Controller.prototype.refresh;
	Controller.prototype.refresh = function () {
		const result = original_refresh.call(this);
		apply_refresh(this.frm);
		return result;
	};

	Controller.__posa_sms_patched = true;
})();

frappe.ui.form.on("Payment Reconciliation", {
	posa_payment_source(frm) {
		pos_next.payment_reconciliation.on_payment_source_change(frm);
	},
});

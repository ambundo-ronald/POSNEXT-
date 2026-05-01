function supportsChangeReconciliation(entry) {
	const paymentType = String(entry?.type || "").trim().toLowerCase()
	const modeOfPayment = String(entry?.mode_of_payment || "").trim().toLowerCase()

	return (
		paymentType === "cash" ||
		paymentType === "bank" ||
		modeOfPayment.includes("cash") ||
		modeOfPayment.includes("bank")
	)
}

export function buildBookkeepingPayments(paymentData) {
	const entries = Array.isArray(paymentData?.payments) ? paymentData.payments : []
	let changeToApply = Number.parseFloat(paymentData?.change_amount || 0) || 0

	const payments = entries
		.filter((entry) => !entry.is_customer_credit)
		.map((entry) => ({
			...entry,
			amount: Number.parseFloat(entry.amount || 0) || 0,
		}))

	for (let index = payments.length - 1; index >= 0 && changeToApply > 0; index -= 1) {
		const payment = payments[index]
		if (!supportsChangeReconciliation(payment) || payment.amount <= 0) {
			continue
		}

		const changeApplied = Math.min(payment.amount, changeToApply)
		payment.amount = Number.parseFloat((payment.amount - changeApplied).toFixed(2))
		changeToApply = Number.parseFloat((changeToApply - changeApplied).toFixed(2))
	}

	return payments
		.filter((entry) => entry.amount > 0)
		.map((entry) => {
			const referenceNo = String(
				entry.reference_no ||
					entry.sms_transaction_id ||
					entry.mpesa_transaction_id ||
					"",
			).trim()

			return {
				mode_of_payment: entry.mode_of_payment,
				amount: entry.amount,
				account: entry.account,
				reference_no: referenceNo || null,
			}
		})
}

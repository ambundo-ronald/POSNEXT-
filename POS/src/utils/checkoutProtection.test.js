import { beforeEach, describe, expect, it } from "vitest"
import {
	clearActiveCheckout,
	createCheckoutFingerprint,
	findRecentMatchingCheckout,
	getActiveCheckout,
	recordCompletedCheckout,
	saveActiveCheckout,
} from "./checkoutProtection"

describe("checkout protection", () => {
	beforeEach(() => {
		window.localStorage.clear()
	})

	it("treats item and payment ordering as the same checkout", () => {
		const base = {
			posProfile: "Shop",
			customer: "Walk-in",
			grandTotal: 300,
		}
		const first = createCheckoutFingerprint({
			...base,
			items: [
				{ item_code: "A", quantity: 1, rate: 100 },
				{ item_code: "B", quantity: 1, rate: 200 },
			],
			payments: [
				{ mode_of_payment: "Cash", amount: 100 },
				{ mode_of_payment: "M-Pesa", amount: 200 },
			],
		})
		const second = createCheckoutFingerprint({
			...base,
			items: [
				{ item_code: "B", quantity: 1, rate: 200 },
				{ item_code: "A", quantity: 1, rate: 100 },
			],
			payments: [
				{ mode_of_payment: "M-Pesa", amount: 200 },
				{ mode_of_payment: "Cash", amount: 100 },
			],
		})

		expect(second).toBe(first)
	})

	it("reuses only an unchanged active checkout", () => {
		saveActiveCheckout("Shop", {
			transaction_id: "posnext-one",
			fingerprint: "same-cart",
			created_at: 1_000,
		})

		expect(getActiveCheckout("Shop", "same-cart", 2_000)?.transaction_id).toBe(
			"posnext-one",
		)
		expect(getActiveCheckout("Shop", "changed-cart", 2_000)).toBeNull()

		clearActiveCheckout("Shop", "posnext-one")
		expect(getActiveCheckout("Shop", "same-cart", 2_000)).toBeNull()
	})

	it("warns only for a recently completed matching checkout", () => {
		recordCompletedCheckout({
			transaction_id: "posnext-complete",
			fingerprint: "same-cart",
			invoice_name: "SINV-0001",
			completed_at: 10_000,
		})

		expect(findRecentMatchingCheckout("same-cart", 10_001)?.invoice_name).toBe(
			"SINV-0001",
		)
		expect(findRecentMatchingCheckout("other-cart", 10_001)).toBeNull()
		expect(findRecentMatchingCheckout("same-cart", 500_000)).toBeNull()
	})
})

const ACTIVE_CHECKOUT_KEY = "pos_next_active_checkout"
const RECENT_CHECKOUTS_KEY = "pos_next_recent_checkouts"
const ACTIVE_CHECKOUT_MAX_AGE_MS = 30 * 60 * 1000
const RECENT_CHECKOUT_WINDOW_MS = 3 * 60 * 1000
const MAX_RECENT_CHECKOUTS = 20
const memoryStorage = new Map()

function getStorage() {
	if (typeof window === "undefined") return null
	try {
		return window.localStorage
	} catch {
		return null
	}
}

function readJson(key, fallback) {
	const storage = getStorage()

	try {
		const value = storage?.getItem(key) || memoryStorage.get(key)
		return JSON.parse(value) || fallback
	} catch {
		return fallback
	}
}

function writeJson(key, value) {
	const serialized = JSON.stringify(value)
	memoryStorage.set(key, serialized)

	const storage = getStorage()
	try {
		storage?.setItem(key, serialized)
	} catch {
		// In-memory protection still covers the current browser session.
	}
}

function normalizeNumber(value) {
	const number = Number.parseFloat(value)
	return Number.isFinite(number) ? Number(number.toFixed(2)) : 0
}

function sortedCopy(rows) {
	return [...rows].sort((left, right) =>
		JSON.stringify(left).localeCompare(JSON.stringify(right)),
	)
}

export function createCheckoutFingerprint({
	posProfile,
	customer,
	grandTotal,
	items = [],
	payments = [],
}) {
	return JSON.stringify({
		pos_profile: posProfile || "",
		customer: customer?.name || customer || "",
		grand_total: normalizeNumber(grandTotal),
		items: sortedCopy(
			items.map((item) => ({
				item_code: item.item_code || "",
				qty: normalizeNumber(item.quantity ?? item.qty),
				rate: normalizeNumber(item.rate),
				uom: item.uom || "",
				warehouse: item.warehouse || "",
				batch_no: item.batch_no || "",
				serial_no: item.serial_no || "",
				discount_percentage: normalizeNumber(item.discount_percentage),
				discount_amount: normalizeNumber(item.discount_amount),
			})),
		),
		payments: sortedCopy(
			payments.map((payment) => ({
				mode_of_payment: payment.mode_of_payment || "",
				amount: normalizeNumber(payment.amount),
				reference_no: payment.reference_no || "",
				mpesa_payment_name: payment.mpesa_payment_name || "",
				sms_payment_name: payment.sms_payment_name || "",
			})),
		),
	})
}

export function createClientTransactionId() {
	const uuid =
		globalThis.crypto?.randomUUID?.() ||
		`${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
	return `posnext-${uuid}`
}

export function getActiveCheckout(posProfile, fingerprint, now = Date.now()) {
	const activeByProfile = readJson(ACTIVE_CHECKOUT_KEY, {})
	const active = activeByProfile[posProfile || ""]

	if (
		!active ||
		active.fingerprint !== fingerprint ||
		now - active.created_at > ACTIVE_CHECKOUT_MAX_AGE_MS
	) {
		return null
	}

	return active
}

export function saveActiveCheckout(posProfile, checkout) {
	const activeByProfile = readJson(ACTIVE_CHECKOUT_KEY, {})
	activeByProfile[posProfile || ""] = checkout
	writeJson(ACTIVE_CHECKOUT_KEY, activeByProfile)
}

export function clearActiveCheckout(posProfile, transactionId) {
	const activeByProfile = readJson(ACTIVE_CHECKOUT_KEY, {})
	const key = posProfile || ""
	if (activeByProfile[key]?.transaction_id !== transactionId) return

	delete activeByProfile[key]
	writeJson(ACTIVE_CHECKOUT_KEY, activeByProfile)
}

export function findRecentMatchingCheckout(fingerprint, now = Date.now()) {
	const recent = readJson(RECENT_CHECKOUTS_KEY, [])
	return (
		recent.find(
			(checkout) =>
				checkout.fingerprint === fingerprint &&
				now - checkout.completed_at <= RECENT_CHECKOUT_WINDOW_MS,
		) || null
	)
}

export function recordCompletedCheckout(checkout) {
	const recent = readJson(RECENT_CHECKOUTS_KEY, [])
	const withoutTransaction = recent.filter(
		(entry) => entry.transaction_id !== checkout.transaction_id,
	)
	writeJson(
		RECENT_CHECKOUTS_KEY,
		[checkout, ...withoutTransaction].slice(0, MAX_RECENT_CHECKOUTS),
	)
}

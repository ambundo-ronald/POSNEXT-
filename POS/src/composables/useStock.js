/**
 * Stock Composable
 *
 * Provides centralized stock-related utilities including stock status
 * badge styling based on quantity levels.
 *
 * Usage:
 * import { useStock } from '@/composables/useStock'
 * const { getStockStatus } = useStock()
 * const status = getStockStatus(item.actual_qty)
 */

/**
 * Round a stock quantity to 3 decimals, removing float noise from
 * cart reservations (e.g. 4.999999 -> 5).
 *
 * @param {number|null|undefined} qty
 * @returns {number}
 */
export function normalizeStockQty(qty) {
	return Math.round((Number(qty) || 0) * 1000) / 1000
}

/**
 * Format a stock quantity for display, showing decimals only when needed
 * (e.g. 12 -> "12", 0.5 -> "0.5", 7.25 -> "7.25").
 *
 * @param {number|null|undefined} qty
 * @returns {string}
 */
export function formatStockQty(qty) {
	return String(normalizeStockQty(qty))
}

export function useStock() {
	/**
	 * Get stock status information based on quantity
	 *
	 * @param {number|null|undefined} qty - The stock quantity
	 * @param {number} lowStockThreshold - Threshold for low stock warning (default: 10)
	 * @param {number} criticalThreshold - Quantities below this show red (default: 6)
	 * @returns {Object} Stock status with level, color, textColor, qtyColor (plain text, no badge), and label
	 */
	function getStockStatus(qty, lowStockThreshold = 10, criticalThreshold = 6) {
		const quantity = normalizeStockQty(qty)

		if (quantity < 0) {
			return {
				level: "negative",
				color: "bg-red-500",
				textColor: "text-white",
				qtyColor: "text-red-600",
				label: __("Negative Stock"),
			}
		}

		if (quantity === 0) {
			return {
				level: "out",
				color: "bg-red-500",
				textColor: "text-white",
				qtyColor: "text-red-600",
				label: __("Out of Stock"),
			}
		}

		if (quantity < criticalThreshold) {
			return {
				level: "critical",
				color: "bg-red-500",
				textColor: "text-white",
				qtyColor: "text-red-600",
				label: __("Low Stock"),
			}
		}

		if (quantity <= lowStockThreshold) {
			return {
				level: "low",
				color: "bg-amber-500",
				textColor: "text-white",
				qtyColor: "text-amber-600",
				label: __("Low Stock"),
			}
		}

		return {
			level: "safe",
			color: "bg-green-500",
			textColor: "text-white",
			qtyColor: "text-green-600",
			label: __("In Stock"),
		}
	}

	return {
		getStockStatus,
		formatStockQty,
		normalizeStockQty,
	}
}

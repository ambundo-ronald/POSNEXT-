/**
 * Tax Conversion Utilities
 * Handles conversion between tax-inclusive and tax-exclusive pricing modes
 */

/**
 * Convert cart prices between tax-inclusive and tax-exclusive modes
 * 
 * When converting TO tax-inclusive (exclusive -> inclusive):
 *   - Gross Price = Net Price × (1 + tax_rate)
 *   - Tax Amount = Net Price × tax_rate
 * 
 * When converting TO tax-exclusive (inclusive -> exclusive):
 *   - Net Price = Gross Price / (1 + tax_rate)
 *   - Tax Amount = Gross Price - Net Price
 * 
 * @param {Array} items - Cart items to convert
 * @param {Number} taxRate - Total tax rate as percentage (e.g., 16 for 16%)
 * @param {String} fromMode - 'inclusive' or 'exclusive' - current mode
 * @param {String} toMode - 'inclusive' or 'exclusive' - target mode
 * @returns {Array} Converted items with new prices and tax amounts
 */
export function convertCartTaxMode(items, taxRate, fromMode, toMode) {
	if (fromMode === toMode) {
		return items.map(item => ({ ...item }))
	}

	const taxMultiplier = 1 + (taxRate / 100)
	const conversionFactor = toMode === 'inclusive' ? taxMultiplier : 1 / taxMultiplier

	return items.map(item => {
		const convertedItem = { ...item }
		const priceListRate = item.price_list_rate || item.rate

		if (toMode === 'inclusive') {
			// Converting from exclusive to inclusive
			// New price = Old price × (1 + tax_rate)
			convertedItem.price_list_rate = priceListRate * taxMultiplier
			convertedItem.rate = priceListRate * taxMultiplier
			
			// Tax is now embedded in price, but shown separately
			const baseAmount = item.quantity * priceListRate
			convertedItem.tax_amount = (baseAmount * taxRate) / 100
		} else {
			// Converting from inclusive to exclusive
			// New price = Old price / (1 + tax_rate)
			convertedItem.price_list_rate = priceListRate / taxMultiplier
			convertedItem.rate = priceListRate / taxMultiplier
			
			// Tax is added on top
			const baseAmount = item.quantity * (priceListRate / taxMultiplier)
			convertedItem.tax_amount = (baseAmount * taxRate) / 100
		}

		// Recalculate discount if present
		if (item.discount_percentage > 0 || item.discount_amount > 0) {
			const baseAmount = item.quantity * convertedItem.price_list_rate
			const discountAmount = item.discount_percentage > 0
				? (baseAmount * item.discount_percentage) / 100
				: item.discount_amount

			convertedItem.discount_amount = discountAmount
			convertedItem.discount_percentage = baseAmount > 0 ? (discountAmount / baseAmount) * 100 : 0
		}

		return convertedItem
	})
}

/**
 * Calculate conversion preview for display
 * Shows what prices will look like after conversion
 * 
 * @param {Array} items - Cart items
 * @param {Number} taxRate - Total tax rate percentage
 * @param {String} currentMode - Current tax mode: 'inclusive' or 'exclusive'
 * @returns {Object} Preview with before/after prices and tax
 */
export function getConversionPreview(items, taxRate, currentMode) {
	if (!items || items.length === 0 || !taxRate) {
		return null
	}

	const targetMode = currentMode === 'inclusive' ? 'exclusive' : 'inclusive'
	const taxMultiplier = 1 + (taxRate / 100)

	let currentSubtotal = 0
	let currentTaxTotal = 0
	let currentGrandTotal = 0
	let newSubtotal = 0
	let newTaxTotal = 0
	let newGrandTotal = 0

	for (const item of items) {
		const priceListRate = item.price_list_rate || item.rate
		const baseAmount = item.quantity * priceListRate

		if (currentMode === 'inclusive') {
			// Currently inclusive - subtotal includes tax
			currentSubtotal += baseAmount
			const extractedTax = baseAmount - (baseAmount / taxMultiplier)
			const extractedNet = baseAmount / taxMultiplier
			currentTaxTotal += extractedTax
			currentGrandTotal += baseAmount

			// After conversion to exclusive
			newSubtotal += extractedNet
			newTaxTotal += extractedTax
			newGrandTotal += baseAmount // Will be same as currentGrandTotal (minus discounts)
		} else {
			// Currently exclusive
			currentSubtotal += baseAmount
			const taxOnThis = (baseAmount * taxRate) / 100
			currentTaxTotal += taxOnThis
			currentGrandTotal += baseAmount + taxOnThis

			// After conversion to inclusive
			newSubtotal += baseAmount * taxMultiplier
			newTaxTotal += taxOnThis
			newGrandTotal += baseAmount + taxOnThis // Will be same (minus discounts)
		}
	}

	return {
		currentMode,
		targetMode,
		taxRate,
		current: {
			subtotal: currentSubtotal,
			tax: currentTaxTotal,
			grandTotal: currentGrandTotal,
			displayFormat: currentMode === 'inclusive' 
				? `Subtotal (inc. tax) + Separate Tax`
				: `Subtotal + Tax on top`
		},
		new: {
			subtotal: newSubtotal,
			tax: newTaxTotal,
			grandTotal: newGrandTotal,
			displayFormat: targetMode === 'inclusive'
				? `Subtotal (inc. tax) + Separate Tax`
				: `Subtotal + Tax on top`
		},
		priceChange: {
			hasIncrease: newSubtotal > currentSubtotal,
			hasDecrease: newSubtotal < currentSubtotal,
			percentageChange: currentSubtotal > 0 
				? ((newSubtotal - currentSubtotal) / currentSubtotal) * 100
				: 0
		}
	}
}

/**
 * Validate if conversion is safe
 * Checks for edge cases that might cause issues
 * 
 * @param {Array} items - Cart items
 * @param {Number} taxRate - Tax rate
 * @returns {Object} Validation result with warnings/errors
 */
export function validateTaxConversion(items, taxRate) {
	const issues = []
	const warnings = []

	if (!items || items.length === 0) {
		issues.push('Cart is empty')
		return { valid: false, issues, warnings }
	}

	if (!taxRate || taxRate <= 0) {
		issues.push('Tax rate not configured or is zero')
		return { valid: false, issues, warnings }
	}

	if (taxRate >= 100) {
		warnings.push('Tax rate is very high (≥100%)')
	}

	// Check for items with discounts
	const itemsWithDiscounts = items.filter(item => 
		item.discount_percentage > 0 || item.discount_amount > 0
	)
	if (itemsWithDiscounts.length > 0) {
		warnings.push(`${itemsWithDiscounts.length} item(s) have discounts - will be recalculated`)
	}

	// Check for items with very small prices (might have rounding issues)
	const verySmallPrices = items.filter(item => {
		const price = item.price_list_rate || item.rate
		return price > 0 && price < 0.01
	})
	if (verySmallPrices.length > 0) {
		warnings.push(`${verySmallPrices.length} item(s) have very small prices - rounding may occur`)
	}

	return {
		valid: issues.length === 0,
		issues,
		warnings
	}
}

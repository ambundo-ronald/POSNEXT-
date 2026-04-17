<template>
	<div class="tax-mode-converter">
		<!-- Control Section -->
		<div class="flex items-center gap-3 p-4 bg-gradient-to-r from-amber-50 to-orange-50 rounded-lg border-2 border-amber-200">
			<div class="flex-1">
				<h4 class="font-semibold text-gray-900 mb-1">
					{{ __('Tax Mode Display') }}
				</h4>
				<p class="text-sm text-gray-600">
					{{ taxModeLabel }}
				</p>
			</div>

			<!-- Toggle and Convert Button -->
			<div class="flex items-center gap-2">
				<!-- Current Mode Badge -->
				<div :class="[
					'px-3 py-1.5 rounded-full font-semibold text-sm flex items-center gap-2',
					taxInclusive ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800'
				]">
					<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
						<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm0-2a6 6 0 100-12 6 6 0 000 12z" clip-rule="evenodd"/>
					</svg>
					{{ taxInclusive ? __('Tax Inclusive') : __('Tax Exclusive') }}
				</div>

				<!-- Convert Button -->
				<Button
					@click="openConvertDialog"
					:disabled="isEmpty"
					variant="outline"
					theme="amber"
					size="sm"
				>
					<template #prefix>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12M8 11h12M8 15h12M3 7h.01M3 11h.01M3 15h.01"/>
						</svg>
					</template>
					{{ __('Convert') }}
				</Button>
			</div>
		</div>

		<!-- Conversion Dialog -->
		<div v-if="showConvertDialog" class="fixed inset-0 bg-black bg-opacity-50 z-[500] flex items-center justify-center p-4">
			<div class="bg-white rounded-lg shadow-2xl max-w-2xl w-full overflow-hidden">
				<!-- Header -->
				<div class="px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-amber-50 to-orange-50">
					<h3 class="text-lg font-bold text-gray-900">
						{{ __('Convert Tax Mode') }}
					</h3>
					<p class="text-sm text-gray-600 mt-1">
						{{ __('Convert prices from {0} to {1}', [
							taxInclusive ? __('Tax Inclusive') : __('Tax Exclusive'),
							taxInclusive ? __('Tax Exclusive') : __('Tax Inclusive')
						]) }}
					</p>
				</div>

				<!-- Content -->
				<div class="p-6 space-y-6 max-h-[70vh] overflow-y-auto">
					<!-- Warnings/Issues -->
					<div v-if="validationResult && validationResult.issues.length > 0" class="p-4 bg-red-50 border border-red-200 rounded-lg">
						<div class="flex items-start gap-3">
							<svg class="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4v2m0 4v2M6 9h12m-12 4h12m-12 4h12"/>
							</svg>
							<div>
								<p class="font-medium text-red-900">{{ __('Issues') }}</p>
								<ul class="mt-2 space-y-1 text-sm text-red-800">
									<li v-for="(issue, idx) in validationResult.issues" :key="idx">
										• {{ issue }}
									</li>
								</ul>
							</div>
						</div>
					</div>

					<div v-if="validationResult && validationResult.warnings.length > 0" class="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
						<div class="flex items-start gap-3">
							<svg class="w-5 h-5 text-yellow-600 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4v2m0 4v2M6 9h12m-12 4h12m-12 4h12"/>
							</svg>
							<div>
								<p class="font-medium text-yellow-900">{{ __('Warnings') }}</p>
								<ul class="mt-2 space-y-1 text-sm text-yellow-800">
									<li v-for="(warning, idx) in validationResult.warnings" :key="idx">
										• {{ warning }}
									</li>
								</ul>
							</div>
						</div>
					</div>

					<!-- Preview Table -->
					<div v-if="preview" class="overflow-x-auto">
						<table class="w-full text-sm">
							<thead>
								<tr class="bg-gray-50 border-b-2 border-gray-200">
									<th class="px-4 py-2 text-left font-semibold text-gray-900">{{ __('Metric') }}</th>
									<th class="px-4 py-2 text-right font-semibold text-gray-900">{{ __('Current') }}</th>
									<th class="px-4 py-2 text-center">
										<svg class="w-4 h-4 inline text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
										</svg>
									</th>
									<th class="px-4 py-2 text-right font-semibold text-gray-900">{{ __('After Conversion') }}</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-gray-200">
								<!-- Subtotal -->
								<tr class="hover:bg-gray-50">
									<td class="px-4 py-3 font-medium text-gray-900">{{ __('Subtotal') }}</td>
									<td class="px-4 py-3 text-right text-gray-600">
										{{ formatCurrency(preview.current.subtotal) }}
									</td>
									<td class="px-4 py-3 text-center">
										<svg v-if="preview.priceChange.hasIncrease" class="w-4 h-4 text-red-500 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8L5 21"/>
										</svg>
										<svg v-else-if="preview.priceChange.hasDecrease" class="w-4 h-4 text-green-500 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 17h8m0 0v-8m0 8L5 3"/>
										</svg>
										<span v-else class="text-gray-400">—</span>
									</td>
									<td class="px-4 py-3 text-right font-semibold text-gray-900">
										{{ formatCurrency(preview.new.subtotal) }}
									</td>
								</tr>

								<!-- Tax -->
								<tr class="hover:bg-gray-50 bg-blue-50/50">
									<td class="px-4 py-3 font-medium text-gray-900">{{ __('Tax ({0}%)', [preview.taxRate]) }}</td>
									<td class="px-4 py-3 text-right text-gray-600">
										{{ formatCurrency(preview.current.tax) }}
									</td>
									<td class="px-4 py-3 text-center text-gray-400">=</td>
									<td class="px-4 py-3 text-right font-semibold text-gray-900">
										{{ formatCurrency(preview.new.tax) }}
									</td>
								</tr>

								<!-- Grand Total -->
								<tr class="bg-gray-100 border-t-2 border-gray-200">
									<td class="px-4 py-3 font-bold text-gray-900">{{ __('Grand Total') }}</td>
									<td class="px-4 py-3 text-right font-bold text-gray-900">
										{{ formatCurrency(preview.current.grandTotal) }}
									</td>
									<td class="px-4 py-3 text-center">
										<svg class="w-4 h-4 text-gray-500 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
										</svg>
									</td>
									<td class="px-4 py-3 text-right font-bold text-gray-900">
										{{ formatCurrency(preview.new.grandTotal) }}
									</td>
								</tr>
							</tbody>
						</table>
					</div>

					<!-- Price Change Summary -->
					<div class="p-4 bg-blue-50 border border-blue-200 rounded-lg" v-if="preview">
						<p class="text-sm text-gray-900">
							<span v-if="Math.abs(preview.priceChange.percentageChange) < 0.01" class="font-semibold">
								{{ __('✓ Prices remain the same (grand total unchanged)') }}
							</span>
							<span v-else-if="preview.priceChange.hasIncrease" class="font-semibold text-red-700">
								{{ __('⚠ Unit prices will increase by {0}%', [preview.priceChange.percentageChange.toFixed(2)]) }}
							</span>
							<span v-else class="font-semibold text-green-700">
								{{ __('✓ Unit prices will decrease by {0}%', [Math.abs(preview.priceChange.percentageChange).toFixed(2)]) }}
							</span>
						</p>
						<p class="text-xs text-gray-600 mt-2">
							{{ preview.current.displayFormat }} 
							<svg class="w-3 h-3 inline text-gray-400 mx-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
							</svg>
							{{ preview.new.displayFormat }}
						</p>
					</div>

					<!-- Info Box -->
					<div class="p-4 bg-gray-50 border border-gray-200 rounded-lg">
						<p class="text-xs font-mono text-gray-700 leading-relaxed">
							<strong>{{ __('How it works:') }}</strong><br>
							<span v-if="taxInclusive">
								{{ __('Currently: Prices INCLUDE tax') }}<br>
								{{ __('After: Prices will EXCLUDE tax (tax shown separately)') }}<br>
								{{ __('Formula: Net Price = Current Price ÷ (1 + tax rate)') }}
							</span>
							<span v-else>
								{{ __('Currently: Prices EXCLUDE tax') }}<br>
								{{ __('After: Prices will INCLUDE tax') }}<br>
								{{ __('Formula: Gross Price = Current Price × (1 + tax rate)') }}
							</span>
						</p>
					</div>
				</div>

				<!-- Actions -->
				<div class="px-6 py-4 border-t border-gray-200 flex gap-3 justify-end bg-gray-50">
					<Button
						@click="closeDialog"
						variant="ghost"
					>
						{{ __('Cancel') }}
					</Button>
					<Button
						@click="performConversion"
						variant="solid"
						theme="amber"
						:loading="converting"
						:disabled="validationResult && !validationResult.valid"
					>
						<template #prefix>
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3v-6"/>
							</svg>
						</template>
						{{ __('Convert Now') }}
					</Button>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Button } from 'frappe-ui'
import { usePOSCartStore } from '@/stores/posCart'
import { useToast } from '@/composables/useToast'
import { convertCartTaxMode, getConversionPreview, validateTaxConversion } from '@/utils/taxConversion'
import { logger } from '@/utils/logger'

const log = logger.create('TaxModeConverter')

const cartStore = usePOSCartStore()
const { showSuccess, showError, showWarning } = useToast()

// State
const showConvertDialog = ref(false)
const converting = ref(false)
const preview = ref(null)
const validationResult = ref(null)

// Format currency function
const formatCurrency = (amount) => {
	return new Intl.NumberFormat('en-US', {
		style: 'currency',
		currency: 'USD'
	}).format(amount)
}

// Computed properties
const taxInclusive = computed(() => cartStore.taxInclusive)
const isEmpty = computed(() => cartStore.isEmpty)
const invoiceItems = computed(() => cartStore.invoiceItems)

const taxModeLabel = computed(() => {
	if (taxInclusive.value) {
		return __('Prices include tax. Tax is divided from prices at checkout.')
	} else {
		return __('Prices exclude tax. Tax is added at checkout.')
	}
})

// Methods
function openConvertDialog() {
	if (isEmpty.value) {
		showWarning(__('Cart is empty'))
		return
	}

	// Validate conversion
	validationResult.value = validateTaxConversion(invoiceItems.value, getTaxRate())

	// Generate preview
	preview.value = getConversionPreview(
		invoiceItems.value,
		getTaxRate(),
		taxInclusive.value ? 'inclusive' : 'exclusive'
	)

	showConvertDialog.value = true
}

function closeDialog() {
	showConvertDialog.value = false
	preview.value = null
	validationResult.value = null
}

function getTaxRate() {
	// Get total tax rate from cart store
	const totalTax = cartStore.totalTax || 0
	const subtotal = cartStore.subtotal || 0

	if (taxInclusive.value && subtotal > 0) {
		// For inclusive mode, tax is embedded - calculate effective rate
		return (totalTax / (subtotal - totalTax)) * 100 || 0
	} else if (subtotal > 0) {
		// For exclusive mode, tax is on top
		return (totalTax / subtotal) * 100 || 0
	}

	return 0
}

async function performConversion() {
	converting.value = true

	try {
		const taxRate = getTaxRate()

		if (!taxRate || taxRate <= 0) {
			showError(__('Tax rate not configured'))
			return
		}

		// Convert items
		const convertedItems = convertCartTaxMode(
			invoiceItems.value,
			taxRate,
			taxInclusive.value ? 'inclusive' : 'exclusive',
			taxInclusive.value ? 'exclusive' : 'inclusive'
		)

		// Update cart items
		cartStore.invoiceItems = convertedItems

		// Toggle tax inclusive mode
		cartStore.setTaxInclusive(!taxInclusive.value)

		// Show success message
		showSuccess(
			__('Tax mode converted to {0}', [
				taxInclusive.value ? __('Tax Exclusive') : __('Tax Inclusive')
			])
		)

		log.info('Tax mode converted successfully', {
			from: taxInclusive.value ? 'exclusive' : 'inclusive',
			to: taxInclusive.value ? 'inclusive' : 'exclusive',
			itemCount: convertedItems.length,
			taxRate
		})

		closeDialog()
	} catch (error) {
		log.error('Error during tax conversion:', error)
		showError(__('Failed to convert tax mode'))
	} finally {
		converting.value = false
	}
}
</script>

<style scoped>
.tax-mode-converter {
	@apply w-full;
}
</style>

<template>
	<Dialog
		v-model="show"
		:options="{ title: __('Invoice Details'), size: '5xl' }"
	>
		<template #body-content>
			<div v-if="loading" class="text-center py-12">
				<div class="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500 mx-auto"></div>
				<p class="mt-3 text-sm text-gray-500">{{ __('Loading invoice details...') }}</p>
			</div>

			<div v-else-if="invoiceData" class="flex flex-col gap-6">
				<!-- Invoice Header -->
				<div class="bg-gradient-to-r from-indigo-50 to-blue-50 rounded-lg p-4 md:p-5 border border-indigo-100">
					<div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
						<div class="flex-1">
							<div class="flex items-center gap-3 mb-2 flex-wrap">
								<h3 class="text-lg md:text-xl font-bold text-gray-900">{{ invoiceData.name }}</h3>
								<span
									v-if="invoiceData.is_return"
									class="px-3 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800"
								>
									{{ __('Return Invoice') }}
								</span>
								<span
									v-else
									:class="[
										'px-3 py-1 text-xs font-semibold rounded-full',
										getInvoiceStatusColor(invoiceData)
									]"
								>
									{{ __(invoiceData.status) }}
								</span>
							</div>
							<div class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
								<div class="text-start">
									<span class="text-gray-600">{{ __('Customer:') }}</span>
									<span class="ms-2 font-semibold text-gray-900">{{ invoiceData.customer_name || invoiceData.customer }}</span>
								</div>
								<div class="text-start">
									<span class="text-gray-600">{{ __('Date:') }}</span>
									<span class="ms-2 font-medium text-gray-900">{{ formatDate(invoiceData.posting_date) }} {{ formatTime(invoiceData.posting_time) }}</span>
								</div>
								<div v-if="invoiceData.return_against" class="text-start">
									<span class="text-gray-600">{{ __('Return Against:') }}</span>
									<span class="ms-2 font-medium text-gray-900">{{ invoiceData.return_against }}</span>
								</div>
							</div>
						</div>
						<div class="text-start sm:text-end">
							<div class="text-xs text-gray-500 mb-1">{{ __('Grand Total') }}</div>
							<div class="text-xl md:text-2xl font-bold text-indigo-600">
								{{ formatCurrency(invoiceData.grand_total) }}
							</div>
						</div>
					</div>
				</div>

				<!-- Credit Sale Return Notice -->
				<div v-if="invoiceData.is_return && isCreditSaleReturn" class="bg-gradient-to-r rtl:bg-gradient-to-l from-blue-50 to-indigo-50 rounded-lg p-4 border border-blue-200">
					<div class="flex flex-row-reverse items-start gap-3">
						<div class="w-8 h-8 rounded-full bg-blue-200 flex items-center justify-center flex-shrink-0">
							<svg class="w-4 h-4 text-blue-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
							</svg>
						</div>
						<div class="text-end flex-1">
							<h4 class="text-sm font-semibold text-blue-900">{{ __('Credit Sale Return') }}</h4>
							<p class="text-xs text-blue-700 mt-1">
								{{ __('This return was against a Pay on Account invoice. The accounts receivable balance has been reversed. No cash refund was processed.') }}
							</p>
						</div>
					</div>
				</div>

				<!-- Pay on Account Notice (for original credit sales) -->
				<div v-else-if="!invoiceData.is_return && isCreditSale" class="bg-gradient-to-r rtl:bg-gradient-to-l from-amber-50 to-orange-50 rounded-lg p-4 border border-amber-200">
					<div class="flex flex-row-reverse items-start gap-3">
						<div class="w-8 h-8 rounded-full bg-amber-200 flex items-center justify-center flex-shrink-0">
							<svg class="w-4 h-4 text-amber-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
							</svg>
						</div>
						<div class="text-end flex-1">
							<h4 class="text-sm font-semibold text-amber-900">{{ __('Pay on Account') }}</h4>
							<p class="text-xs text-amber-700 mt-1">
								{{ __('This invoice was sold on credit. The customer owes the full amount.') }}
							</p>
						</div>
					</div>
				</div>

				<!-- Items Section -->
				<div>
					<h4 class="text-sm font-semibold text-gray-700 mb-3 flex items-center">
						<svg class="w-4 h-4 me-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
						</svg>
						{{ __('Items') }}
					</h4>
					<!-- Mobile Cards View -->
					<div class="md:hidden flex flex-col gap-3">
						<div
							v-for="(item, idx) in invoiceData.items"
							:key="idx"
							class="bg-white border border-gray-200 rounded-lg p-3"
						>
							<!-- Item Name & Amount Row -->
							<div class="flex items-center justify-between gap-3 mb-2">
								<div class="flex-1 min-w-0 text-center">
									<div class="text-sm font-semibold text-gray-900">{{ item.item_name }}</div>
									<div class="text-xs text-gray-500">{{ item.item_code }}</div>
								</div>
							</div>
							<!-- Details Grid -->
							<div class="grid grid-cols-3 gap-2 text-center border-t border-gray-100 pt-2">
								<div>
									<div class="text-xs text-gray-500">{{ __('Qty') }}</div>
									<div class="text-sm font-medium text-gray-900">{{ item.quantity }}</div>
								</div>
								<div>
									<div class="text-xs text-gray-500">{{ __('Rate') }}</div>
									<div class="text-sm font-medium text-gray-900">{{ formatCurrency(item.rate) }}</div>
								</div>
								<div>
									<div class="text-xs text-gray-500">{{ __('Amount') }}</div>
									<div class="text-sm font-semibold text-gray-900">{{ formatCurrency(item.amount) }}</div>
								</div>
							</div>
							<!-- Discount Row (if applicable) -->
							<div v-if="item.discount_percentage" class="text-center text-xs text-orange-600 mt-2 pt-2 border-t border-gray-100">
								{{ __('Discount:') }} {{ item.discount_percentage }}%
							</div>
						</div>
					</div>
					<!-- Desktop Table View -->
					<div class="hidden md:block border border-gray-200 rounded-lg overflow-hidden">
						<table class="min-w-full divide-y divide-gray-200">
							<thead class="bg-gray-50">
								<tr>
									<th class="px-4 py-3 text-center text-xs font-semibold text-gray-600 uppercase tracking-wider">{{ __('Item') }}</th>
									<th class="px-4 py-3 text-center text-xs font-semibold text-gray-600 uppercase tracking-wider">{{ __('Qty') }}</th>
									<th class="px-4 py-3 text-center text-xs font-semibold text-gray-600 uppercase tracking-wider">{{ __('Rate') }}</th>
									<th class="px-4 py-3 text-center text-xs font-semibold text-gray-600 uppercase tracking-wider">{{ __('Discount') }}</th>
									<th class="px-4 py-3 text-center text-xs font-semibold text-gray-600 uppercase tracking-wider">{{ __('Amount') }}</th>
								</tr>
							</thead>
							<tbody class="bg-white divide-y divide-gray-200">
								<tr v-for="(item, idx) in invoiceData.items" :key="idx" class="hover:bg-gray-50">
									<td class="px-4 py-3 text-center">
										<div class="text-sm font-medium text-gray-900">{{ item.item_name }}</div>
										<div class="text-xs text-gray-500">{{ item.item_code }}</div>
									</td>
									<td class="px-4 py-3 text-center text-sm text-gray-900">{{ item.quantity }}</td>
									<td class="px-4 py-3 text-center text-sm text-gray-900">{{ formatCurrency(item.rate) }}</td>
									<td class="px-4 py-3 text-center text-sm text-gray-600">
										{{ item.discount_percentage ? `${item.discount_percentage}%` : '-' }}
									</td>
									<td class="px-4 py-3 text-center text-sm font-semibold text-gray-900">{{ formatCurrency(item.amount) }}</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>

				<!-- Totals Section -->
				<div class="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
					<!-- Payment Info -->
					<div v-if="invoiceData.payments && invoiceData.payments.length > 0">
						<h4 class="text-sm font-semibold text-gray-700 mb-3 flex items-center">
							<svg class="w-4 h-4 me-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/>
							</svg>
							{{ __('Payments') }}
						</h4>
						<div class="flex flex-col gap-2">
							<div
								v-for="(payment, idx) in invoiceData.payments"
								:key="idx"
								class="flex justify-between items-center p-3 bg-green-50 border border-green-200 rounded-lg"
							>
								<div class="text-start">
									<div class="text-sm font-medium text-gray-900">{{ payment.mode_of_payment }}</div>
									<div v-if="payment.account" class="text-xs text-gray-500">{{ payment.account }}</div>
								</div>
								<div class="text-sm font-semibold text-green-700">{{ formatCurrency(payment.amount) }}</div>
							</div>
						</div>
					</div>

					<!-- Summary -->
					<div>
						<h4 class="text-sm font-semibold text-gray-700 mb-3 text-start">{{ __('Summary') }}</h4>
						<div class="flex flex-col gap-2 bg-gray-50 p-4 rounded-lg border border-gray-200">
							<div class="flex justify-between text-sm">
								<span class="text-gray-600">{{ __('Net Total:') }}</span>
								<span class="font-medium text-gray-900">{{ formatCurrency(invoiceData.net_total || invoiceData.total) }}</span>
							</div>
							<div v-if="invoiceData.total_taxes_and_charges" class="flex justify-between text-sm">
								<span class="text-gray-600">{{ __('Taxes:') }}</span>
								<span class="font-medium text-gray-900">{{ formatCurrency(invoiceData.total_taxes_and_charges) }}</span>
							</div>
							<div v-if="invoiceData.discount_amount" class="flex justify-between text-sm">
								<span class="text-gray-600">{{ __('Discount:') }}</span>
								<span class="font-medium text-red-600">-{{ formatCurrency(invoiceData.discount_amount) }}</span>
							</div>
							<div class="pt-2 border-t border-gray-300 flex justify-between">
								<span class="font-semibold text-gray-900">{{ __('Grand Total:') }}</span>
								<span class="font-bold text-lg text-indigo-600">{{ formatCurrency(invoiceData.grand_total) }}</span>
							</div>
							<div v-if="invoiceData.paid_amount" class="flex justify-between text-sm">
								<span class="text-gray-600">{{ __('Paid Amount:') }}</span>
								<span class="font-semibold text-green-600">{{ formatCurrency(invoiceData.paid_amount) }}</span>
							</div>
							<!-- For return invoices with negative outstanding (credit to customer) -->
							<div v-if="invoiceData.is_return && invoiceData.outstanding_amount < 0" class="flex justify-between text-sm">
								<span class="text-gray-600">{{ __('Customer Credit:') }}</span>
								<span class="font-semibold text-blue-600">{{ formatCurrency(Math.abs(invoiceData.outstanding_amount)) }}</span>
							</div>
							<!-- For regular invoices with outstanding (customer owes) -->
							<div v-else-if="invoiceData.outstanding_amount && invoiceData.outstanding_amount > 0" class="flex justify-between text-sm">
								<span class="text-gray-600">{{ __('Outstanding:') }}</span>
								<span class="font-semibold text-orange-600">{{ formatCurrency(invoiceData.outstanding_amount) }}</span>
							</div>
						</div>
					</div>
				</div>

				<!-- Payment Recovery -->
				<div v-if="canCreatePaymentEntry" class="border border-blue-100 bg-blue-50 rounded-lg p-4">
					<div class="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
						<div class="text-start">
							<h4 class="text-sm font-semibold text-blue-900">{{ __('Recover Payment') }}</h4>
							<p class="text-xs text-blue-700 mt-1">
								{{ __('Create a Payment Entry from pending SMS Enabler payments for this invoice.') }}
							</p>
							<p class="text-xs font-semibold text-blue-900 mt-2">
								{{ __('Outstanding:') }} {{ formatCurrency(invoiceData.outstanding_amount) }}
							</p>
						</div>
						<Button
							variant="solid"
							theme="blue"
							@click="openSmsPaymentMatcher"
						>
							{{ showSmsPaymentMatcher ? __('Refresh Matches') : __('Create Payment Entry') }}
						</Button>
					</div>

					<div v-if="showSmsPaymentMatcher" class="mt-4 bg-white border border-blue-100 rounded-lg p-3">
						<div class="flex flex-col md:flex-row gap-3 md:items-center md:justify-between">
							<input
								v-model="smsMatchSearch"
								type="text"
								class="w-full md:flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-400"
								:placeholder="__('Search payer, phone, transaction ID, or account reference')"
								@input="scheduleSmsPaymentSearch"
							/>
							<div class="text-xs text-gray-600 md:text-end">
								{{ __('Selected:') }} {{ selectedSmsPaymentNames.length }}
								<span class="font-semibold text-gray-900 ms-1">{{ formatCurrency(selectedSmsTotal) }}</span>
							</div>
						</div>

						<div v-if="smsMatchLoading" class="text-center py-6 text-sm text-gray-500">
							{{ __('Loading pending SMS payments...') }}
						</div>

						<div v-else-if="smsPaymentMatches.length === 0" class="text-center py-6 text-sm text-gray-500">
							{{ __('No pending SMS payments found for this invoice amount.') }}
						</div>

						<div v-else class="mt-3 border border-gray-200 rounded-lg overflow-hidden max-h-72 overflow-y-auto">
							<button
								v-for="payment in smsPaymentMatches"
								:key="payment.name"
								type="button"
								class="w-full flex items-center justify-between gap-3 px-3 py-3 border-b border-gray-100 last:border-b-0 text-start hover:bg-blue-50"
								:class="{ 'bg-blue-50': isSmsPaymentSelected(payment.name) }"
								@click="toggleSmsPaymentSelection(payment)"
							>
								<div class="flex items-start gap-3 min-w-0">
									<input
										type="checkbox"
										class="mt-1"
										:checked="isSmsPaymentSelected(payment.name)"
										@click.stop
										@change="toggleSmsPaymentSelection(payment)"
									/>
									<div class="min-w-0">
										<div class="flex flex-wrap items-center gap-2">
											<span class="text-sm font-semibold text-gray-900 truncate">
												{{ payment.payer_name || payment.sender || payment.name }}
											</span>
											<span
												v-if="payment.is_exact_amount"
												class="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700"
											>
												{{ __('Exact') }}
											</span>
											<span class="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
												{{ payment.match_level || __('Low') }}
											</span>
										</div>
										<div class="text-xs text-gray-500 mt-1 truncate">
											{{ payment.transaction_id || payment.name }}
											<span v-if="payment.payer_phone"> | {{ payment.payer_phone }}</span>
											<span v-if="payment.account_reference"> | {{ payment.account_reference }}</span>
										</div>
										<div v-if="payment.match_reasons && payment.match_reasons.length" class="text-xs text-blue-700 mt-1">
											{{ payment.match_reasons.join(', ') }}
										</div>
									</div>
								</div>
								<div class="text-end flex-shrink-0">
									<div class="text-sm font-bold text-gray-900">{{ formatCurrency(payment.amount) }}</div>
									<div class="text-xs text-gray-500">{{ formatPaymentReceivedAt(payment.received_at) }}</div>
								</div>
							</button>
						</div>

						<div class="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mt-4">
							<div class="text-xs text-gray-600">
								{{ __('This creates submitted ERPNext Payment Entries and consumes the selected SMS records.') }}
							</div>
							<div class="flex gap-2 justify-end">
								<Button variant="subtle" @click="closeSmsPaymentMatcher">
									{{ __('Cancel') }}
								</Button>
								<Button
									variant="solid"
									theme="green"
									:loading="reconcilingSmsPayments"
									:disabled="selectedSmsPaymentNames.length === 0 || reconcilingSmsPayments"
									@click="reconcileSelectedSmsPayments"
								>
									{{ __('Reconcile Payment') }}
								</Button>
							</div>
						</div>
					</div>
				</div>

				<!-- Additional Info -->
				<div v-if="invoiceData.remarks" class="bg-gray-50 p-4 rounded-lg border border-gray-200">
					<h4 class="text-sm font-semibold text-gray-700 mb-2 text-start">{{ __('Remarks') }}</h4>
					<p class="text-sm text-gray-600 text-start">{{ invoiceData.remarks }}</p>
				</div>
			</div>

			<div v-else class="text-center py-12">
				<svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
				</svg>
				<p class="mt-2 text-sm text-gray-500">{{ __('Failed to load invoice details') }}</p>
			</div>
		</template>
		<template #actions>
			<div class="flex justify-between items-center w-full">
				<Button variant="subtle" @click="show = false">
					{{ __('Close') }}
				</Button>
				<Button @click="handlePrint">
					<template #prefix>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"/>
						</svg>
					</template>
					{{ __('Print') }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { useFormatters } from "@/composables/useFormatters"
import { useToast } from "@/composables/useToast"
import { formatCurrency as formatCurrencyUtil } from "@/utils/currency"
import { getInvoiceStatusColor } from "@/utils/invoice"
import { logger } from "@/utils/logger"
import { Button, Dialog, call } from "frappe-ui"
import { ref, watch, nextTick, computed } from "vue"

const log = logger.create('InvoiceDetailDialog')
const { formatDate, formatTime } = useFormatters()
const { showSuccess, showError, showWarning } = useToast()

const props = defineProps({
	modelValue: Boolean,
	invoiceName: String,
	posProfile: String,
	currency: {
		type: String,
		default: "USD",
	},
})

function formatCurrency(amount) {
	return formatCurrencyUtil(Number.parseFloat(amount || 0), props.currency)
}

const emit = defineEmits(["update:modelValue", "print-invoice", "payment-reconciled"])

const show = ref(props.modelValue)
const loading = ref(false)
const invoiceData = ref(null)
const showSmsPaymentMatcher = ref(false)
const smsMatchLoading = ref(false)
const smsMatchSearch = ref("")
const smsPaymentMatches = ref([])
const selectedSmsPaymentNames = ref([])
const reconcilingSmsPayments = ref(false)
let smsSearchTimer = null

// Computed: Check if this is a credit sale (Pay on Account - no payments, full outstanding)
const isCreditSale = computed(() => {
	if (!invoiceData.value) return false
	const hasNoPayments = !invoiceData.value.payments || invoiceData.value.payments.length === 0
	const totalPaid = invoiceData.value.payments?.reduce((sum, p) => sum + Math.abs(p.amount || 0), 0) || 0
	const grandTotal = Math.abs(invoiceData.value.grand_total || 0)
	const outstanding = Math.abs(invoiceData.value.outstanding_amount || 0)
	// Credit sale if no payments and outstanding equals grand total
	return hasNoPayments || (totalPaid < 0.01 && Math.abs(outstanding - grandTotal) < 0.01)
})

// Computed: Check if this is a credit sale return (return with no payments)
const isCreditSaleReturn = computed(() => {
	if (!invoiceData.value || !invoiceData.value.is_return) return false
	const hasNoPayments = !invoiceData.value.payments || invoiceData.value.payments.length === 0
	const totalPaid = invoiceData.value.payments?.reduce((sum, p) => sum + Math.abs(p.amount || 0), 0) || 0
	return hasNoPayments || totalPaid < 0.01
})

const canCreatePaymentEntry = computed(() => {
	if (!invoiceData.value) return false
	return (
		Number(invoiceData.value.docstatus) === 1 &&
		!invoiceData.value.is_return &&
		Number(invoiceData.value.outstanding_amount || 0) > 0.01
	)
})

const selectedSmsPayments = computed(() => {
	const selected = new Set(selectedSmsPaymentNames.value)
	return smsPaymentMatches.value.filter((payment) => selected.has(payment.name))
})

const selectedSmsTotal = computed(() => {
	return selectedSmsPayments.value.reduce((sum, payment) => sum + Number(payment.amount || 0), 0)
})

watch(
	() => props.modelValue,
	(val) => {
		show.value = val
		if (val && props.invoiceName) {
			loadInvoiceDetails()
		}
	},
)

watch(show, async (val) => {
	emit("update:modelValue", val)
	if (!val) {
		// Clear data when closing
		invoiceData.value = null
		resetSmsPaymentMatcher()
	} else {
		// Ensure dialog appears above other dialogs
		await nextTick()
		const dialogs = document.querySelectorAll('.modal-container, .modal-backdrop')
		dialogs.forEach(dialog => {
			const title = dialog.querySelector('[class*="title"]')
			if (title && title.textContent?.includes('Invoice Details')) {
				dialog.style.zIndex = '400'
			}
		})
	}
})

async function loadInvoiceDetails() {
	if (!props.invoiceName) return

	loading.value = true
	try {
		const result = await call("pos_next.api.invoices.get_invoice", {
			invoice_name: props.invoiceName,
		})

		// Map server 'qty' to 'quantity' for internal consistency
		if (result && result.items) {
			result.items = result.items.map((item) => ({
				...item,
				quantity: item.qty,
			}))
		}
		invoiceData.value = result
		if (!canCreatePaymentEntry.value) {
			resetSmsPaymentMatcher()
		}
	} catch (error) {
		log.error("Error loading invoice details:", error)
		invoiceData.value = null
		resetSmsPaymentMatcher()
	} finally {
		loading.value = false
	}
}

function handlePrint() {
	if (!invoiceData.value) return
	emit("print-invoice", invoiceData.value)
}

function resetSmsPaymentMatcher() {
	showSmsPaymentMatcher.value = false
	smsMatchLoading.value = false
	smsMatchSearch.value = ""
	smsPaymentMatches.value = []
	selectedSmsPaymentNames.value = []
	reconcilingSmsPayments.value = false
	if (smsSearchTimer) {
		clearTimeout(smsSearchTimer)
		smsSearchTimer = null
	}
}

async function openSmsPaymentMatcher() {
	if (!canCreatePaymentEntry.value) return
	showSmsPaymentMatcher.value = true
	await loadSmsPaymentMatches()
}

function closeSmsPaymentMatcher() {
	showSmsPaymentMatcher.value = false
	selectedSmsPaymentNames.value = []
}

function scheduleSmsPaymentSearch() {
	if (smsSearchTimer) {
		clearTimeout(smsSearchTimer)
	}
	smsSearchTimer = setTimeout(() => {
		loadSmsPaymentMatches()
	}, 250)
}

async function loadSmsPaymentMatches() {
	if (!invoiceData.value || !canCreatePaymentEntry.value) return

	smsMatchLoading.value = true
	try {
		const result = await call("pos_next.api.smsenabler_mpesa.get_sms_payment_matches_for_invoice", {
			invoice: invoiceData.value.name,
			search: smsMatchSearch.value,
		})
		smsPaymentMatches.value = result?.payments || []
		const available = new Set(smsPaymentMatches.value.map((payment) => payment.name))
		selectedSmsPaymentNames.value = selectedSmsPaymentNames.value.filter((name) => available.has(name))
	} catch (error) {
		log.error("Error loading SMS payment matches:", error)
		showError(getErrorMessage(error) || __("Failed to load SMS payments"))
	} finally {
		smsMatchLoading.value = false
	}
}

function isSmsPaymentSelected(name) {
	return selectedSmsPaymentNames.value.includes(name)
}

function toggleSmsPaymentSelection(payment) {
	const name = payment?.name
	if (!name) return
	if (isSmsPaymentSelected(name)) {
		selectedSmsPaymentNames.value = selectedSmsPaymentNames.value.filter((item) => item !== name)
	} else {
		selectedSmsPaymentNames.value = [...selectedSmsPaymentNames.value, name]
	}
}

async function reconcileSelectedSmsPayments() {
	if (!invoiceData.value || selectedSmsPaymentNames.value.length === 0) {
		showWarning(__("Select an SMS payment first"))
		return
	}

	const outstanding = Number(invoiceData.value.outstanding_amount || 0)
	if (selectedSmsTotal.value > outstanding + 0.01) {
		showError(__("Selected payments exceed the invoice outstanding amount"))
		return
	}

	reconcilingSmsPayments.value = true
	try {
		const result = await call("pos_next.api.smsenabler_mpesa.reconcile_invoice_with_sms_payments", {
			invoice: invoiceData.value.name,
			sms_payments: selectedSmsPaymentNames.value,
		})

		showSuccess(__("Payment Entry created and invoice reconciled"))
		selectedSmsPaymentNames.value = []
		smsPaymentMatches.value = []
		showSmsPaymentMatcher.value = false
		await loadInvoiceDetails()
		emit("payment-reconciled", result)
	} catch (error) {
		log.error("Error reconciling SMS payment:", error)
		showError(getErrorMessage(error) || __("Failed to reconcile payment"))
	} finally {
		reconcilingSmsPayments.value = false
	}
}

function formatPaymentReceivedAt(value) {
	if (!value) return ""
	return String(value).replace("T", " ").slice(0, 16)
}

function getErrorMessage(error) {
	if (!error) return ""
	if (Array.isArray(error.messages) && error.messages.length) {
		return error.messages.join(" ")
	}
	return error.message || error.exc || ""
}
</script>


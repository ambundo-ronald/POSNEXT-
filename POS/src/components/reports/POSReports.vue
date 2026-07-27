<template>
	<Transition name="fade">
		<div
			v-if="show"
			class="fixed inset-0 bg-black bg-opacity-50 z-[300]"
			@click.self="handleClose"
		>
			<div class="fixed inset-0 flex items-center justify-center p-4">
				<div class="w-full h-full max-w-[94vw] max-h-[92vh] bg-white rounded-lg shadow-2xl overflow-hidden flex flex-col">
					<div class="flex flex-col gap-4 px-6 py-5 border-b bg-white md:flex-row md:items-center md:justify-between">
						<div class="flex items-center gap-3">
							<div class="p-2 bg-orange-100 rounded-lg">
								<FeatherIcon name="bar-chart-2" class="w-6 h-6 text-orange-600" />
							</div>
							<div>
								<h2 class="text-xl font-bold text-gray-900">{{ __("Reports") }}</h2>
								<p class="text-sm text-gray-600">{{ posProfile }}</p>
							</div>
						</div>

						<div class="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end">
							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-gray-600">{{ __("From") }}</span>
								<input
									v-model="fromDate"
									type="date"
									class="h-9 rounded-md border border-gray-300 px-3 text-sm focus:border-orange-500 focus:outline-none focus:ring-2 focus:ring-orange-100"
								/>
							</label>
							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-gray-600">{{ __("To") }}</span>
								<input
									v-model="toDate"
									type="date"
									class="h-9 rounded-md border border-gray-300 px-3 text-sm focus:border-orange-500 focus:outline-none focus:ring-2 focus:ring-orange-100"
								/>
							</label>
							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-gray-600">{{ __("Sales Person") }}</span>
								<select
									v-model="selectedSalesPerson"
									class="h-9 min-w-44 rounded-md border border-gray-300 bg-white px-3 text-sm focus:border-orange-500 focus:outline-none focus:ring-2 focus:ring-orange-100"
								>
									<option value="">{{ __("All Sales Persons") }}</option>
									<option
										v-for="salesPerson in salesPersons"
										:key="salesPerson"
										:value="salesPerson"
									>
										{{ salesPerson }}
									</option>
								</select>
							</label>
							<Button
								@click="loadReport"
								:loading="loading"
								variant="solid"
							>
								<template #prefix>
									<FeatherIcon name="refresh-cw" class="w-4 h-4" />
								</template>
								{{ __("Refresh") }}
							</Button>
							<Button
								v-if="canViewCashFigures"
								@click="exportReport('xlsx')"
								:loading="exporting === 'xlsx'"
								:disabled="loading || Boolean(exporting)"
								variant="outline"
							>
								<template #prefix>
									<FeatherIcon name="download" class="w-4 h-4" />
								</template>
								{{ __("Excel") }}
							</Button>
							<Button
								v-if="canViewCashFigures"
								@click="exportReport('pdf')"
								:loading="exporting === 'pdf'"
								:disabled="loading || Boolean(exporting)"
								variant="outline"
							>
								<template #prefix>
									<FeatherIcon name="download" class="w-4 h-4" />
								</template>
								{{ __("PDF") }}
							</Button>
							<Button variant="ghost" @click="handleClose" icon="x">
								<template #icon>
									<FeatherIcon name="x" class="w-4 h-4" />
								</template>
							</Button>
						</div>
					</div>

					<div class="flex-1 overflow-y-auto bg-gray-50">
						<div v-if="loading && !hasReport" class="flex flex-col items-center justify-center py-20">
							<div class="animate-spin rounded-full h-12 w-12 border-b-3 border-orange-500 mb-4"></div>
							<p class="text-sm font-medium text-gray-600">{{ __("Loading report...") }}</p>
						</div>

						<div v-else class="p-6 flex flex-col gap-6">
							<div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
								<div
									v-for="metric in metrics"
									:key="metric.key"
									class="bg-white border border-gray-200 rounded-lg p-4 shadow-sm"
								>
									<div class="flex items-center justify-between gap-3">
										<div>
											<p class="text-xs font-medium text-gray-500">{{ metric.label }}</p>
											<p class="mt-2 text-2xl font-bold text-gray-900">{{ metric.value }}</p>
										</div>
										<div :class="['p-2 rounded-lg', metric.iconBg]">
											<FeatherIcon :name="metric.icon" :class="['w-5 h-5', metric.iconColor]" />
										</div>
									</div>
									<p v-if="metric.caption" class="mt-2 text-xs text-gray-500">{{ metric.caption }}</p>
								</div>
							</div>

							<div class="grid gap-6 xl:grid-cols-[1fr_1fr]">
								<section class="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
									<div class="px-5 py-4 border-b bg-gray-50 flex items-center justify-between">
										<div>
											<h3 class="text-sm font-bold text-gray-900">{{ __("Payment Methods") }}</h3>
											<p class="text-xs text-gray-500">{{ __("Collected amounts by method") }}</p>
										</div>
										<FeatherIcon name="credit-card" class="w-5 h-5 text-gray-500" />
									</div>
									<div v-if="!canViewCashFigures" class="px-5 py-10 text-center text-sm text-gray-500">
										{{ __("Cash and payment totals are visible to Sales Manager only") }}
									</div>
									<div v-else-if="paymentMethods.length" class="divide-y divide-gray-100">
										<div
											v-for="method in paymentMethods"
											:key="method.mode_of_payment"
											class="px-5 py-3 flex items-center justify-between gap-4"
										>
											<div class="min-w-0">
												<p class="text-sm font-semibold text-gray-900 truncate">{{ method.mode_of_payment }}</p>
												<p class="text-xs text-gray-500">{{ __("{0} entries", [method.count || 0]) }}</p>
											</div>
											<p class="text-sm font-bold text-green-600">{{ formatCurrency(method.amount) }}</p>
										</div>
									</div>
									<div v-else class="px-5 py-10 text-center text-sm text-gray-500">
										{{ __("No payments found for this period") }}
									</div>
								</section>

								<section class="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
									<div class="px-5 py-4 border-b bg-gray-50 flex items-center justify-between">
										<div>
											<h3 class="text-sm font-bold text-gray-900">{{ __("Top Items") }}</h3>
											<p class="text-xs text-gray-500">{{ __("Best sellers by sales amount") }}</p>
										</div>
										<FeatherIcon name="package" class="w-5 h-5 text-gray-500" />
									</div>
									<div v-if="topItems.length" class="divide-y divide-gray-100">
										<div
											v-for="item in topItems"
											:key="item.item_code"
											class="px-5 py-3 grid grid-cols-[1fr_auto] gap-4"
										>
											<div class="min-w-0">
												<p class="text-sm font-semibold text-gray-900 truncate">{{ item.item_name || item.item_code }}</p>
												<p class="text-xs text-gray-500">{{ item.item_code }}</p>
											</div>
											<div class="text-end">
												<p class="text-sm font-bold text-gray-900">{{ formatCurrency(item.amount) }}</p>
												<p class="text-xs text-gray-500">{{ __("{0} qty", [formatNumber(item.quantity)]) }}</p>
											</div>
										</div>
									</div>
									<div v-else class="px-5 py-10 text-center text-sm text-gray-500">
										{{ __("No item sales found for this period") }}
									</div>
								</section>
							</div>

							<section class="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
								<div class="px-5 py-4 border-b bg-gray-50 flex items-center justify-between">
									<div>
										<h3 class="text-sm font-bold text-gray-900">{{ __("Recent Invoices") }}</h3>
										<p class="text-xs text-gray-500">{{ __("Latest invoices in the selected period") }}</p>
									</div>
									<FeatherIcon name="file-text" class="w-5 h-5 text-gray-500" />
								</div>
								<div v-if="recentInvoices.length" class="overflow-x-auto">
									<table class="min-w-full divide-y divide-gray-200">
										<thead class="bg-white">
											<tr>
												<th class="px-5 py-3 text-start text-xs font-semibold text-gray-500">{{ __("Invoice") }}</th>
												<th class="px-5 py-3 text-start text-xs font-semibold text-gray-500">{{ __("Customer") }}</th>
												<th class="px-5 py-3 text-start text-xs font-semibold text-gray-500">{{ __("Sales Person") }}</th>
												<th class="px-5 py-3 text-start text-xs font-semibold text-gray-500">{{ __("Date") }}</th>
												<th class="px-5 py-3 text-end text-xs font-semibold text-gray-500">{{ __("Total") }}</th>
												<th class="px-5 py-3 text-end text-xs font-semibold text-gray-500">{{ __("Outstanding") }}</th>
											</tr>
										</thead>
										<tbody class="divide-y divide-gray-100 bg-white">
											<tr v-for="invoice in recentInvoices" :key="invoice.name">
												<td class="px-5 py-3 text-sm font-semibold text-gray-900">
													<div class="flex items-center gap-2">
														<span>{{ invoice.name }}</span>
														<span
															v-if="invoice.is_return"
															class="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-red-100 text-red-700"
														>
															{{ __("Return") }}
														</span>
													</div>
												</td>
												<td class="px-5 py-3 text-sm text-gray-700">{{ invoice.customer_name || invoice.customer }}</td>
												<td class="px-5 py-3 text-sm text-gray-700">{{ invoice.sales_person || __("Unassigned") }}</td>
												<td class="px-5 py-3 text-sm text-gray-600">{{ formatDate(invoice.posting_date) }}</td>
												<td class="px-5 py-3 text-sm font-semibold text-end text-gray-900">{{ formatCurrency(invoice.grand_total) }}</td>
												<td class="px-5 py-3 text-sm font-semibold text-end text-orange-600">{{ canViewCashFigures ? formatCurrency(invoice.outstanding_amount) : __("Restricted") }}</td>
											</tr>
										</tbody>
									</table>
								</div>
								<div v-else class="px-5 py-10 text-center text-sm text-gray-500">
									{{ __("No invoices found for this period") }}
								</div>
							</section>
						</div>
					</div>
				</div>
			</div>
		</div>
	</Transition>
</template>

<script setup>
import { useFormatters } from "@/composables/useFormatters"
import { useToast } from "@/composables/useToast"
import { call } from "@/utils/apiWrapper"
import { formatCurrency as formatCurrencyUtil } from "@/utils/currency"
import { Button, FeatherIcon } from "frappe-ui"
import { computed, ref, watch } from "vue"

const props = defineProps({
	modelValue: Boolean,
	posProfile: String,
	currency: {
		type: String,
		default: "USD",
	},
})

const emit = defineEmits(["update:modelValue"])

const { formatDate } = useFormatters()
const { showError, showWarning } = useToast()

const show = ref(props.modelValue)
const loading = ref(false)
const exporting = ref("")
const report = ref(null)
const fromDate = ref(getToday())
const toDate = ref(getToday())
const selectedSalesPerson = ref("")

const hasReport = computed(() => Boolean(report.value))
const summary = computed(() => report.value?.summary || {})
const canViewCashFigures = computed(() => report.value?.cash_figures_visible === true)
const paymentMethods = computed(() => canViewCashFigures.value ? report.value?.payment_methods || [] : [])
const salesPersons = computed(() => report.value?.sales_persons || [])
const topItems = computed(() => report.value?.top_items || [])
const recentInvoices = computed(() => report.value?.recent_invoices || [])

const metrics = computed(() => [
	{
		key: "net_sales",
		label: __("Net Sales"),
		value: formatCurrency(summary.value.net_sales),
		caption: __("Gross {0} minus returns {1}", [
			formatCurrency(summary.value.gross_sales),
			formatCurrency(summary.value.returns_total),
		]),
		icon: "trending-up",
		iconBg: "bg-green-100",
		iconColor: "text-green-600",
	},
	{
		key: "paid",
		label: __("Collected"),
		value: canViewCashFigures.value ? formatCurrency(summary.value.paid_amount) : __("Restricted"),
		caption: canViewCashFigures.value
			? __("Outstanding {0}", [formatCurrency(summary.value.outstanding_amount)])
			: __("Visible to Sales Manager only"),
		icon: "credit-card",
		iconBg: "bg-blue-100",
		iconColor: "text-blue-600",
	},
	{
		key: "invoices",
		label: __("Invoices"),
		value: formatNumber(summary.value.invoice_count),
		caption: __("{0} sales, {1} returns", [
			formatNumber(summary.value.sale_count),
			formatNumber(summary.value.return_count),
		]),
		icon: "file-text",
		iconBg: "bg-orange-100",
		iconColor: "text-orange-600",
	},
	{
		key: "items",
		label: __("Items Sold"),
		value: formatNumber(summary.value.quantity),
		caption: __("Discounts {0}", [
			formatCurrency(summary.value.discount_amount),
		]),
		icon: "shopping-bag",
		iconBg: "bg-purple-100",
		iconColor: "text-purple-600",
	},
])

watch(
	() => props.modelValue,
	(value) => {
		show.value = value
		if (value) {
			loadReport()
		}
	},
)

watch(show, (value) => {
	emit("update:modelValue", value)
})

function getToday() {
	const today = new Date()
	const year = today.getFullYear()
	const month = String(today.getMonth() + 1).padStart(2, "0")
	const day = String(today.getDate()).padStart(2, "0")
	return `${year}-${month}-${day}`
}

function handleClose() {
	show.value = false
}

async function loadReport() {
	if (!props.posProfile) return
	if (!validateDateRange()) return

	loading.value = true
	try {
		report.value = await call("pos_next.api.invoices.get_sales_report", {
			pos_profile: props.posProfile,
			from_date: fromDate.value,
			to_date: toDate.value,
			sales_person: selectedSalesPerson.value,
			limit: 10,
		})
	} catch (error) {
		console.error("Failed to load POS reports:", error)
		report.value = null
	} finally {
		loading.value = false
	}
}

function validateDateRange() {
	if (!fromDate.value || !toDate.value) {
		showWarning(__("Select both From and To dates"))
		return false
	}
	if (fromDate.value > toDate.value) {
		showWarning(__("From Date cannot be after To Date"))
		return false
	}
	return true
}

async function exportReport(fileType) {
	if (!props.posProfile || !validateDateRange() || exporting.value) return

	exporting.value = fileType
	try {
		const params = new URLSearchParams({
			pos_profile: props.posProfile,
			from_date: fromDate.value,
			to_date: toDate.value,
			file_type: fileType,
			sales_person: selectedSalesPerson.value,
		})
		const response = await fetch(
			`/api/method/pos_next.api.invoices.export_sales_report?${params.toString()}`,
			{ credentials: "same-origin" },
		)
		if (!response.ok) {
			throw new Error(__("The report could not be exported"))
		}

		const blob = await response.blob()
		const safeProfile = props.posProfile
			.toLowerCase()
			.replace(/[^a-z0-9]+/g, "-")
			.replace(/^-|-$/g, "")
		const filename = `pos-sales-${safeProfile || "report"}-${fromDate.value}-to-${toDate.value}.${fileType}`
		const objectUrl = URL.createObjectURL(blob)
		const link = document.createElement("a")
		link.href = objectUrl
		link.download = filename
		document.body.appendChild(link)
		link.click()
		link.remove()
		window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0)
	} catch (error) {
		console.error("Failed to export POS report:", error)
		showError(error.message || __("The report could not be exported"))
	} finally {
		exporting.value = ""
	}
}

function formatCurrency(amount) {
	return formatCurrencyUtil(Number.parseFloat(amount || 0), props.currency)
}

function formatNumber(value) {
	return new Intl.NumberFormat().format(Number.parseFloat(value || 0))
}
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
	transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
	opacity: 0;
}
</style>

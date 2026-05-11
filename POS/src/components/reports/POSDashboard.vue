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
							<div class="p-2 bg-blue-100 rounded-lg">
								<FeatherIcon name="layout" class="w-6 h-6 text-blue-600" />
							</div>
							<div>
								<h2 class="text-xl font-bold text-gray-900">{{ __("Dashboard") }}</h2>
								<p class="text-sm text-gray-600">{{ posProfile }}</p>
							</div>
						</div>

						<div class="flex items-center gap-2">
							<div class="hidden text-end sm:block">
								<p class="text-xs font-medium text-gray-500">{{ __("Today") }}</p>
								<p class="text-sm font-semibold text-gray-900">{{ formatDate(today) }}</p>
							</div>
							<Button
								@click="loadDashboard"
								:loading="loading"
								variant="solid"
							>
								<template #prefix>
									<FeatherIcon name="refresh-cw" class="w-4 h-4" />
								</template>
								{{ __("Refresh") }}
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
							<div class="animate-spin rounded-full h-12 w-12 border-b-3 border-blue-500 mb-4"></div>
							<p class="text-sm font-medium text-gray-600">{{ __("Loading dashboard...") }}</p>
						</div>

						<div v-else class="p-6 flex flex-col gap-6">
							<div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
								<div
									v-for="metric in metrics"
									:key="metric.key"
									class="bg-white border border-gray-200 rounded-lg p-4 shadow-sm"
								>
									<div class="flex items-center justify-between gap-3">
										<div class="min-w-0">
											<p class="text-xs font-medium text-gray-500">{{ metric.label }}</p>
											<p class="mt-2 text-2xl font-bold text-gray-900 truncate">{{ metric.value }}</p>
										</div>
										<div :class="['p-2 rounded-lg', metric.iconBg]">
											<FeatherIcon :name="metric.icon" :class="['w-5 h-5', metric.iconColor]" />
										</div>
									</div>
									<p class="mt-2 text-xs text-gray-500">{{ metric.caption }}</p>
								</div>
							</div>

							<div class="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
								<section class="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
									<div class="px-5 py-4 border-b bg-gray-50 flex items-center justify-between">
										<div>
											<h3 class="text-sm font-bold text-gray-900">{{ __("Operating Context") }}</h3>
											<p class="text-xs text-gray-500">{{ __("Current profile, shift, and cart") }}</p>
										</div>
										<FeatherIcon name="monitor" class="w-5 h-5 text-gray-500" />
									</div>
									<div class="p-5 grid gap-3">
										<div
											v-for="row in contextRows"
											:key="row.label"
											class="flex items-center justify-between gap-4 rounded-md bg-gray-50 px-3 py-2"
										>
											<span class="text-xs font-medium text-gray-500">{{ row.label }}</span>
											<span class="text-sm font-semibold text-gray-900 text-end truncate">{{ row.value }}</span>
										</div>
									</div>
								</section>

								<section class="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
									<div class="px-5 py-4 border-b bg-gray-50 flex items-center justify-between">
										<div>
											<h3 class="text-sm font-bold text-gray-900">{{ __("Payment Mix") }}</h3>
											<p class="text-xs text-gray-500">{{ __("Collections for today") }}</p>
										</div>
										<FeatherIcon name="credit-card" class="w-5 h-5 text-gray-500" />
									</div>
									<div v-if="paymentMethods.length" class="p-5 flex flex-col gap-3">
										<div
											v-for="method in paymentMethods"
											:key="method.mode_of_payment"
											class="grid gap-2"
										>
											<div class="flex items-center justify-between gap-4">
												<span class="text-sm font-semibold text-gray-900 truncate">{{ method.mode_of_payment }}</span>
												<span class="text-sm font-bold text-green-600">{{ formatCurrency(method.amount) }}</span>
											</div>
											<div class="h-2 rounded-full bg-gray-100 overflow-hidden">
												<div
													class="h-full bg-blue-500"
													:style="{ width: `${getPaymentPercent(method.amount)}%` }"
												></div>
											</div>
										</div>
									</div>
									<div v-else class="px-5 py-10 text-center text-sm text-gray-500">
										{{ __("No collections yet today") }}
									</div>
								</section>
							</div>

							<div class="grid gap-6 xl:grid-cols-[1fr_1fr]">
								<section class="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
									<div class="px-5 py-4 border-b bg-gray-50 flex items-center justify-between">
										<div>
											<h3 class="text-sm font-bold text-gray-900">{{ __("Top Items Today") }}</h3>
											<p class="text-xs text-gray-500">{{ __("Ranked by sales amount") }}</p>
										</div>
										<FeatherIcon name="shopping-bag" class="w-5 h-5 text-gray-500" />
									</div>
									<div v-if="topItems.length" class="divide-y divide-gray-100">
										<div
											v-for="(item, index) in topItems.slice(0, 5)"
											:key="item.item_code"
											class="px-5 py-3 grid grid-cols-[auto_1fr_auto] items-center gap-3"
										>
											<span class="w-7 h-7 rounded-md bg-blue-50 text-blue-700 text-xs font-bold flex items-center justify-center">
												{{ index + 1 }}
											</span>
											<div class="min-w-0">
												<p class="text-sm font-semibold text-gray-900 truncate">{{ item.item_name || item.item_code }}</p>
												<p class="text-xs text-gray-500">{{ __("{0} qty", [formatNumber(item.quantity)]) }}</p>
											</div>
											<p class="text-sm font-bold text-gray-900">{{ formatCurrency(item.amount) }}</p>
										</div>
									</div>
									<div v-else class="px-5 py-10 text-center text-sm text-gray-500">
										{{ __("No item sales yet today") }}
									</div>
								</section>

								<section class="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
									<div class="px-5 py-4 border-b bg-gray-50 flex items-center justify-between">
										<div>
											<h3 class="text-sm font-bold text-gray-900">{{ __("Recent Activity") }}</h3>
											<p class="text-xs text-gray-500">{{ __("Latest submitted invoices") }}</p>
										</div>
										<FeatherIcon name="clock" class="w-5 h-5 text-gray-500" />
									</div>
									<div v-if="recentInvoices.length" class="divide-y divide-gray-100">
										<div
											v-for="invoice in recentInvoices.slice(0, 6)"
											:key="invoice.name"
											class="px-5 py-3 flex items-center justify-between gap-4"
										>
											<div class="min-w-0">
												<div class="flex items-center gap-2">
													<p class="text-sm font-semibold text-gray-900 truncate">{{ invoice.name }}</p>
													<span
														v-if="invoice.is_return"
														class="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-red-100 text-red-700"
													>
														{{ __("Return") }}
													</span>
												</div>
												<p class="text-xs text-gray-500 truncate">{{ invoice.customer_name || invoice.customer }}</p>
											</div>
											<div class="text-end">
												<p class="text-sm font-bold text-gray-900">{{ formatCurrency(invoice.grand_total) }}</p>
												<p class="text-xs text-gray-500">{{ invoice.status }}</p>
											</div>
										</div>
									</div>
									<div v-else class="px-5 py-10 text-center text-sm text-gray-500">
										{{ __("No invoices yet today") }}
									</div>
								</section>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	</Transition>
</template>

<script setup>
import { useFormatters } from "@/composables/useFormatters"
import { call } from "@/utils/apiWrapper"
import { formatCurrency as formatCurrencyUtil } from "@/utils/currency"
import { Button, FeatherIcon } from "frappe-ui"
import { computed, ref, watch } from "vue"

const props = defineProps({
	modelValue: Boolean,
	posProfile: String,
	posOpeningShift: String,
	warehouse: String,
	company: String,
	currency: {
		type: String,
		default: "USD",
	},
	cartTotal: {
		type: Number,
		default: 0,
	},
	cartItemCount: {
		type: Number,
		default: 0,
	},
	isOffline: Boolean,
})

const emit = defineEmits(["update:modelValue"])

const { formatDate } = useFormatters()

const show = ref(props.modelValue)
const loading = ref(false)
const report = ref(null)
const unpaidSummary = ref(null)
const today = getToday()

const hasReport = computed(() => Boolean(report.value))
const summary = computed(() => report.value?.summary || {})
const paymentMethods = computed(() => report.value?.payment_methods || [])
const topItems = computed(() => report.value?.top_items || [])
const recentInvoices = computed(() => report.value?.recent_invoices || [])

const metrics = computed(() => [
	{
		key: "sales",
		label: __("Today's Net Sales"),
		value: formatCurrency(summary.value.net_sales),
		caption: __("{0} invoices", [formatNumber(summary.value.invoice_count)]),
		icon: "trending-up",
		iconBg: "bg-green-100",
		iconColor: "text-green-600",
	},
	{
		key: "collections",
		label: __("Collected Today"),
		value: formatCurrency(summary.value.paid_amount),
		caption: __("Outstanding today {0}", [formatCurrency(summary.value.outstanding_amount)]),
		icon: "credit-card",
		iconBg: "bg-blue-100",
		iconColor: "text-blue-600",
	},
	{
		key: "receivables",
		label: __("Open Receivables"),
		value: formatCurrency(unpaidSummary.value?.total_outstanding),
		caption: __("{0} unpaid invoices", [formatNumber(unpaidSummary.value?.count)]),
		icon: "alert-circle",
		iconBg: "bg-orange-100",
		iconColor: "text-orange-600",
	},
	{
		key: "cart",
		label: __("Current Cart"),
		value: formatCurrency(props.cartTotal),
		caption: __("{0} items in cart", [formatNumber(props.cartItemCount)]),
		icon: "shopping-cart",
		iconBg: "bg-purple-100",
		iconColor: "text-purple-600",
	},
])

const contextRows = computed(() => [
	{ label: __("Status"), value: props.isOffline ? __("Offline") : __("Online") },
	{ label: __("Company"), value: props.company || "-" },
	{ label: __("Warehouse"), value: props.warehouse || "-" },
	{ label: __("Opening Shift"), value: props.posOpeningShift || "-" },
])

const totalCollected = computed(() =>
	paymentMethods.value.reduce((sum, row) => sum + Number.parseFloat(row.amount || 0), 0),
)

watch(
	() => props.modelValue,
	(value) => {
		show.value = value
		if (value) {
			loadDashboard()
		}
	},
)

watch(show, (value) => {
	emit("update:modelValue", value)
})

function getToday() {
	const now = new Date()
	const year = now.getFullYear()
	const month = String(now.getMonth() + 1).padStart(2, "0")
	const day = String(now.getDate()).padStart(2, "0")
	return `${year}-${month}-${day}`
}

function handleClose() {
	show.value = false
}

async function loadDashboard() {
	if (!props.posProfile) return

	loading.value = true
	try {
		const [reportData, unpaidData] = await Promise.all([
			call("pos_next.api.invoices.get_sales_report", {
				pos_profile: props.posProfile,
				from_date: today,
				to_date: today,
				limit: 8,
			}),
			call("pos_next.api.partial_payments.get_unpaid_summary", {
				pos_profile: props.posProfile,
			}),
		])

		report.value = reportData
		unpaidSummary.value = unpaidData
	} catch (error) {
		console.error("Failed to load POS dashboard:", error)
		report.value = null
		unpaidSummary.value = null
	} finally {
		loading.value = false
	}
}

function getPaymentPercent(amount) {
	if (!totalCollected.value) return 0
	return Math.min(100, Math.round((Number.parseFloat(amount || 0) / totalCollected.value) * 100))
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

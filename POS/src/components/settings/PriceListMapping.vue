<template>
	<div class="price-list-mapping-container">
		<!-- Header -->
		<div class="flex items-center justify-between mb-4">
			<div>
				<h3 class="text-lg font-semibold text-gray-900">
					{{ __('Conditional Price List') }}
				</h3>
				<p class="text-sm text-gray-600 mt-1">
					{{ __('Apply specific price lists based on warehouse and customer group') }}
				</p>
			</div>
			<Button
				@click="openAddDialog"
				variant="solid"
				theme="blue"
				size="sm"
			>
				<template #prefix>
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
					</svg>
				</template>
				{{ __('Add Mapping') }}
			</Button>
		</div>

		<!-- Mappings Table -->
		<div class="bg-white rounded-lg border border-gray-200 overflow-hidden">
			<div v-if="mappings.length === 0" class="p-8 text-center">
				<svg class="w-12 h-12 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m0 0a9 9 0 11-18 0 9 9 0 0118 0z"/>
				</svg>
				<p class="text-gray-600">{{ __('No price list mappings configured') }}</p>
				<p class="text-sm text-gray-500 mt-1">{{ __('Add a mapping to get started') }}</p>
			</div>

			<table v-else class="w-full divide-y divide-gray-200">
				<thead class="bg-gray-50">
					<tr>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
							{{ __('Warehouse') }}
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
							{{ __('Customer Group') }}
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
							{{ __('Price List') }}
						</th>
						<th class="px-6 py-3 text-right text-xs font-medium text-gray-700 uppercase tracking-wider">
							{{ __('Actions') }}
						</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-200">
					<tr
						v-for="mapping in mappings"
						:key="mapping.name"
						class="hover:bg-gray-50 transition-colors"
					>
						<td class="px-6 py-3 text-sm text-gray-900">
							<span class="font-medium">{{ mapping.warehouse }}</span>
						</td>
						<td class="px-6 py-3 text-sm text-gray-900">
							{{ mapping.customer_group }}
						</td>
						<td class="px-6 py-3 text-sm text-gray-900">
							<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
								{{ mapping.price_list }}
							</span>
						</td>
						<td class="px-6 py-3 text-right text-sm space-x-2">
							<button
								@click="editMapping(mapping)"
								class="text-blue-600 hover:text-blue-900 font-medium"
							>
								{{ __('Edit') }}
							</button>
							<button
								@click="deleteMapping(mapping)"
								class="text-red-600 hover:text-red-900 font-medium"
							>
								{{ __('Delete') }}
							</button>
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<!-- Add/Edit Dialog -->
		<div v-if="showDialog" class="fixed inset-0 bg-black bg-opacity-50 z-[400] flex items-center justify-center p-4">
			<div class="bg-white rounded-lg shadow-xl max-w-md w-full">
				<!-- Header -->
				<div class="px-6 py-4 border-b border-gray-200">
					<h3 class="text-lg font-semibold text-gray-900">
						{{ isEditMode ? __('Edit Price List Mapping') : __('Add Price List Mapping') }}
					</h3>
				</div>

				<!-- Form -->
				<div class="p-6 space-y-4">
					<!-- Warehouse Select -->
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-2">
							{{ __('Warehouse') }} <span class="text-red-500">*</span>
						</label>
						<Autocomplete
							v-model="formData.warehouse"
							:options="warehouseOptions"
							:loading="loadingWarehouses"
							@search="searchWarehouses"
							@select="onWarehouseSelect"
							:allow-custom-value="false"
						/>
					</div>

					<!-- Customer Group Select -->
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-2">
							{{ __('Customer Group') }} <span class="text-red-500">*</span>
						</label>
						<Autocomplete
							v-model="formData.customer_group"
							:options="customerGroupOptions"
							:loading="loadingCustomerGroups"
							@search="searchCustomerGroups"
							@select="onCustomerGroupSelect"
							:allow-custom-value="false"
						/>
					</div>

					<!-- Price List Select -->
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-2">
							{{ __('Price List') }} <span class="text-red-500">*</span>
						</label>
						<Autocomplete
							v-model="formData.price_list"
							:options="priceListOptions"
							:loading="loadingPriceLists"
							@search="searchPriceLists"
							@select="onPriceListSelect"
							:allow-custom-value="false"
						/>
					</div>
				</div>

				<!-- Actions -->
				<div class="px-6 py-4 border-t border-gray-200 flex gap-3 justify-end">
					<Button
						@click="closeDialog"
						variant="ghost"
					>
						{{ __('Cancel') }}
					</Button>
					<Button
						@click="saveMapping"
						variant="solid"
						theme="blue"
						:loading="savingMapping"
					>
						{{ __('Save') }}
					</Button>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, onMounted, computed } from "vue"
import { Button, Autocomplete } from "frappe-ui"
import { call } from "@/utils/apiWrapper"
import { useToast } from "@/composables/useToast"

const props = defineProps({
	posProfile: {
		type: String,
		required: true,
	},
})

const emit = defineEmits(["update"])

const { toast } = useToast()

function getResponseMessage(result) {
	return result?.message ?? result
}

// State
const mappings = ref([])
const showDialog = ref(false)
const isEditMode = ref(false)
const savingMapping = ref(false)
const loadingMappings = ref(false)

// Form data
const formData = ref({
	warehouse: "",
	customer_group: "",
	price_list: "",
	name: null,
})

// Autocomplete options and loading states
const warehouseOptions = ref([])
const customerGroupOptions = ref([])
const priceListOptions = ref([])

const loadingWarehouses = ref(false)
const loadingCustomerGroups = ref(false)
const loadingPriceLists = ref(false)

// Load mappings on mount
onMounted(async () => {
	await loadMappings()
})

// Load all mappings for this POS Profile
async function loadMappings() {
	loadingMappings.value = true
	try {
		const result = await call(
			"pos_next.api.price_lists.get_price_list_mappings",
			{
				pos_profile: props.posProfile,
			},
		)

		mappings.value = getResponseMessage(result) || []
		emit("update")
	} catch (error) {
		console.error("Error loading mappings:", error)
		toast("Error loading price list mappings", "error")
	} finally {
		loadingMappings.value = false
	}
}

// Search warehouses
async function searchWarehouses(query) {
	loadingWarehouses.value = true
	try {
		const result = await call("frappe.client.get_list", {
			doctype: "Warehouse",
			fields: ["name"],
			filters: {
				name: ["like", `%${query}%`],
				disabled: 0,
			},
			limit_page_length: 20,
		})

		warehouseOptions.value = (getResponseMessage(result) || []).map((r) => ({
			label: r.name,
			value: r.name,
		}))
	} catch (error) {
		console.error("Error searching warehouses:", error)
	} finally {
		loadingWarehouses.value = false
	}
}

// Search customer groups
async function searchCustomerGroups(query) {
	loadingCustomerGroups.value = true
	try {
		const result = await call("frappe.client.get_list", {
			doctype: "Customer Group",
			fields: ["name"],
			filters: {
				name: ["like", `%${query}%`],
			},
			limit_page_length: 20,
		})

		customerGroupOptions.value = (getResponseMessage(result) || []).map(
			(r) => ({
				label: r.name,
				value: r.name,
			}),
		)
	} catch (error) {
		console.error("Error searching customer groups:", error)
	} finally {
		loadingCustomerGroups.value = false
	}
}

// Search price lists
async function searchPriceLists(query) {
	loadingPriceLists.value = true
	try {
		const result = await call("frappe.client.get_list", {
			doctype: "Price List",
			fields: ["name"],
			filters: {
				name: ["like", `%${query}%`],
				enabled: 1,
			},
			limit_page_length: 20,
		})

		priceListOptions.value = (getResponseMessage(result) || []).map((r) => ({
			label: r.name,
			value: r.name,
		}))
	} catch (error) {
		console.error("Error searching price lists:", error)
	} finally {
		loadingPriceLists.value = false
	}
}

// Event handlers for select
function onWarehouseSelect(warehouse) {
	formData.value.warehouse = warehouse.value
}

function onCustomerGroupSelect(customerGroup) {
	formData.value.customer_group = customerGroup.value
}

function onPriceListSelect(priceList) {
	formData.value.price_list = priceList.value
}

// Open add dialog
function openAddDialog() {
	resetForm()
	isEditMode.value = false
	showDialog.value = true
}

// Edit mapping
function editMapping(mapping) {
	formData.value = {
		warehouse: mapping.warehouse,
		customer_group: mapping.customer_group,
		price_list: mapping.price_list,
		name: mapping.name,
	}
	isEditMode.value = true
	showDialog.value = true
}

// Save mapping
async function saveMapping() {
	// Validate
	if (
		!formData.value.warehouse ||
		!formData.value.customer_group ||
		!formData.value.price_list
	) {
		toast("Please fill in all fields", "error")
		return
	}

	savingMapping.value = true
	try {
		const result = await call(
			"pos_next.api.price_lists.save_price_list_mapping",
			{
				pos_profile: props.posProfile,
				warehouse: formData.value.warehouse,
				customer_group: formData.value.customer_group,
				price_list: formData.value.price_list,
			},
		)
		const message = getResponseMessage(result)

		if (message?.success) {
			toast(message.message, "success")
			closeDialog()
			await loadMappings()
		}
	} catch (error) {
		console.error("Error saving mapping:", error)
		toast("Error saving mapping", "error")
	} finally {
		savingMapping.value = false
	}
}

// Delete mapping
async function deleteMapping(mapping) {
	if (!confirm(__("Are you sure you want to delete this mapping?"))) {
		return
	}

	try {
		const result = await call(
			"pos_next.api.price_lists.delete_price_list_mapping",
			{
				mapping_name: mapping.name,
			},
		)
		const message = getResponseMessage(result)

		if (message?.success) {
			toast(message.message, "success")
			await loadMappings()
		}
	} catch (error) {
		console.error("Error deleting mapping:", error)
		toast("Error deleting mapping", "error")
	}
}

// Reset form
function resetForm() {
	formData.value = {
		warehouse: "",
		customer_group: "",
		price_list: "",
		name: null,
	}
}

// Close dialog
function closeDialog() {
	showDialog.value = false
	resetForm()
	isEditMode.value = false
}
</script>

<style scoped>
.price-list-mapping-container {
	@apply w-full;
}
</style>

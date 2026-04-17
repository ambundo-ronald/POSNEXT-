// Composable for managing conditional price list selection
// Based on warehouse and customer group mappings

import { ref, watch, computed } from 'vue'
import { frappe } from 'frappe'
import { logger } from '@/utils/logger'

const log = logger.create('usePriceListResolver')

export function usePriceListResolver() {
	// State
	const priceLists = ref([])
	const loadingMappings = ref(false)
	const selectedPriceList = ref(null)
	const mappingError = ref(null)

	/**
	 * Load price list mappings for the current POS Profile
	 */
	async function loadMappings(posProfile) {
		if (!posProfile) return

		loadingMappings.value = true
		try {
			const result = await frappe.call({
				method: 'pos_next.api.price_lists.get_price_list_mappings',
				args: {
					pos_profile: posProfile
				}
			})

			priceLists.value = result.message || []
			mappingError.value = null
			log.debug('Loaded price list mappings', { count: priceLists.value.length })
		} catch (error) {
			log.error('Error loading price list mappings:', error)
			mappingError.value = error.message
			priceLists.value = []
		} finally {
			loadingMappings.value = false
		}
	}

	/**
	 * Resolve the appropriate price list for the given warehouse and customer group
	 * 
	 * Returns the mapped price list name if a mapping exists, otherwise null
	 */
	async function resolvePriceList(posProfile, warehouse, customerGroup) {
		if (!posProfile || !warehouse || !customerGroup) {
			log.debug('Cannot resolve price list - missing parameters', {
				posProfile, warehouse, customerGroup
			})
			return null
		}

		try {
			// First try to find in locally loaded mappings for performance
			const localMapping = priceLists.value.find(
				m => m.warehouse === warehouse && m.customer_group === customerGroup
			)

			if (localMapping) {
				log.debug('Found local price list mapping', { 
					warehouse, 
					customerGroup, 
					priceList: localMapping.price_list 
				})
				return localMapping.price_list
			}

			// If not found locally, query server (in case mappings were added by another user)
			const result = await frappe.call({
				method: 'pos_next.api.price_lists.resolve_price_list',
				args: {
					pos_profile: posProfile,
					warehouse: warehouse,
					customer_group: customerGroup
				}
			})

			const resolvedPriceList = result.message

			if (resolvedPriceList) {
				log.debug('Resolved price list from server', {
					warehouse,
					customerGroup,
					priceList: resolvedPriceList
				})
				return resolvedPriceList
			}

			log.debug('No price list mapping found', { warehouse, customerGroup })
			return null
		} catch (error) {
			log.error('Error resolving price list:', error)
			return null
		}
	}

	/**
	 * Find all mappings for a specific warehouse
	 */
	function getMappingsForWarehouse(warehouse) {
		return priceLists.value.filter(m => m.warehouse === warehouse)
	}

	/**
	 * Find all mappings for a specific customer group
	 */
	function getMappingsForCustomerGroup(customerGroup) {
		return priceLists.value.filter(m => m.customer_group === customerGroup)
	}

	/**
	 * Check if there are any mappings configured
	 */
	const hasMappings = computed(() => priceLists.value.length > 0)

	/**
	 * Get summary of configured mappings
	 */
	const mappingsSummary = computed(() => {
		const warehouses = new Set(priceLists.value.map(m => m.warehouse))
		const customerGroups = new Set(priceLists.value.map(m => m.customer_group))

		return {
			totalMappings: priceLists.value.length,
			uniqueWarehouses: warehouses.size,
			uniqueCustomerGroups: customerGroups.size,
			warehouses: Array.from(warehouses),
			customerGroups: Array.from(customerGroups)
		}
	})

	return {
		// State
		priceLists,
		loadingMappings,
		selectedPriceList,
		mappingError,
		hasMappings,
		mappingsSummary,

		// Methods
		loadMappings,
		resolvePriceList,
		getMappingsForWarehouse,
		getMappingsForCustomerGroup
	}
}

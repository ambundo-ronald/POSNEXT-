<template>
	<!-- Full Page Overlay -->
	<Transition name="fade">
		<div
			v-if="show"
			class="fixed inset-0 bg-black bg-opacity-50 z-[300]"
			@click.self="handleClose"
		>
			<!-- Main Container -->
			<div class="fixed inset-0 flex items-center justify-center p-4 md:p-6">
				<div class="w-full max-w-5xl max-h-[90vh] bg-white rounded-xl shadow-2xl overflow-hidden flex flex-col">
					<!-- Header -->
					<div class="flex items-center justify-between px-6 py-5 border-b bg-gradient-to-r from-blue-50 to-indigo-50">
						<div class="flex items-center gap-3">
							<div class="p-2 bg-blue-100 rounded-lg">
								<svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
								</svg>
							</div>
							<div>
								<h2 class="text-xl font-bold text-gray-900">{{ __('POS Settings') }}</h2>
								<p class="text-sm text-gray-600 flex items-center mt-0.5">
									<svg class="w-4 h-4 me-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
									</svg>
									{{ settings.pos_profile || posProfile }}
								</p>
							</div>
						</div>
						<div class="flex items-center gap-2">
							<Button
								@click="loadSettings"
								:loading="loading"
								variant="ghost"
								size="sm"
							>
								<template #prefix>
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
									</svg>
								</template>
								{{ __('Refresh') }}
							</Button>
							<Button
								@click="saveSettings"
								:loading="saving"
								variant="solid"
								theme="blue"
							>
								<template #prefix>
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
									</svg>
								</template>
								{{ __('Save Changes') }}
							</Button>
							<button
								@click="handleClose"
								class="p-2 hover:bg-white/50 rounded-lg transition-colors"
							>
								<svg class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
								</svg>
							</button>
						</div>
					</div>

					<!-- Main Content -->
					<div class="flex-1 overflow-y-auto bg-gray-50">
						<!-- Loading State -->
						<div v-if="loading" class="flex flex-col items-center justify-center py-16">
							<div class="animate-spin rounded-full h-12 w-12 border-b-3 border-blue-500 mb-4"></div>
							<p class="text-sm font-medium text-gray-600">{{ __('Loading settings...') }}</p>
						</div>

						<!-- Settings Form -->
						<div v-else-if="settings.pos_profile || posProfile" class="p-6 flex flex-col gap-6">
							<!-- Tabs Navigation -->
							<div class="flex p-1 bg-gray-200 rounded-lg self-start">
								<button
									@click="activeTab = 'stock'"
									:class="['px-4 py-2 text-sm font-medium rounded-md transition-all duration-200', activeTab === 'stock' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-200/50']"
								>
									{{ __('Stock Management') }}
								</button>
								<button
									@click="activeTab = 'sales'"
									:class="['px-4 py-2 text-sm font-medium rounded-md transition-all duration-200', activeTab === 'sales' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-200/50']"
								>
									{{ __('Sales Management') }}
								</button>
								<button
									@click="activeTab = 'customer'"
									:class="['px-4 py-2 text-sm font-medium rounded-md transition-all duration-200', activeTab === 'customer' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-200/50']"
								>
									{{ __('Customer') }}
								</button>
								<button
									@click="activeTab = 'pricing'"
									:class="['px-4 py-2 text-sm font-medium rounded-md transition-all duration-200', activeTab === 'pricing' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-200/50']"
								>
									{{ __('Pricing Strategy') }}
								</button>
							</div>

							<!-- Stock Settings Section - Prominent -->
							<div v-if="activeTab === 'stock'" class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
								<div :class="stockSectionClasses.header">
									<div class="flex items-center justify-between">
										<div class="flex items-center gap-3">
											<div :class="stockSectionClasses.iconContainer">
												<svg :class="stockSectionClasses.icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="icons.warehouse"/>
												</svg>
											</div>
											<div>
												<h3 class="text-lg font-bold text-gray-900">{{ __('Stock Management') }}</h3>
												<p class="text-xs text-gray-600 mt-0.5">{{ __('Configure warehouse and inventory settings') }}</p>
											</div>
										</div>
										<div :class="stockSectionClasses.badge">
											<svg :class="stockSectionClasses.badgeIcon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="icons.checkCircle"/>
											</svg>
											<span :class="stockSectionClasses.badgeText">{{ __('Stock Controls') }}</span>
										</div>
									</div>
								</div>
								<div class="p-6 flex flex-col gap-6">
									<!-- Warehouse Selection -->
									<div :class="warehouseSubsectionClasses.container">
										<div class="flex items-center gap-2 mb-4">
											<svg :class="warehouseSubsectionClasses.icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="icons.location"/>
											</svg>
											<h4 class="text-sm font-semibold text-gray-900">{{ __('Warehouse Selection') }}</h4>
										</div>
										<div v-if="warehouseOptions.length === 0" class="flex items-center p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
											<svg class="w-5 h-5 text-yellow-600 me-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="icons.warning"/>
											</svg>
											<p class="text-sm text-yellow-800 font-medium">{{ __('Loading warehouses...') }}</p>
										</div>
										<SelectField
											v-else
											v-model="selectedWarehouse"
											:label="__('Active Warehouse')"
											:options="warehouseOptions"
											:description="__('All stock operations will use this warehouse. Stock quantities will refresh after saving.')"
										/>
									</div>

									<!-- Stock Policy Settings -->
									<div :class="stockPolicySubsectionClasses.container">
										<div class="flex items-center gap-2 mb-4">
											<svg :class="stockPolicySubsectionClasses.icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="icons.clipboard"/>
											</svg>
											<h4 class="text-sm font-semibold text-gray-900">{{ __('Stock Validation Policy') }}</h4>
										</div>
										<div class="flex flex-col gap-3">
											<CheckboxField
												v-model="settings.allow_negative_stock"
												:label="__('Allow Negative Stock')"
												:description="__('Enable selling items even when stock reaches zero or below. Integrates with ERPNext stock settings.')"
											/>
											<div class="mt-3 p-3 bg-blue-100 rounded-md">
												<div class="flex items-start gap-2">
													<svg class="w-4 h-4 text-blue-600 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
														<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="icons.info"/>
													</svg>
													<TranslatedHTML 
														:tag="'p'"
														class="text-xs text-blue-800 leading-relaxed" 
														:inner="__('&lt;strong&gt;Note:&lt;strong&gt; When enabled, the system will allow sales even when stock quantity is zero or negative. This is useful for handling stock sync delays or backorders. All transactions are tracked in the stock ledger.')"
													/>
												</div>
											</div>
										</div>
									</div>

									<!-- Background Stock Sync Settings -->
									<div :class="stockSyncSubsectionClasses.container">
										<div class="flex items-center gap-2 mb-4">
											<svg :class="stockSyncSubsectionClasses.icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
											</svg>
											<h4 class="text-sm font-semibold text-gray-900">{{ __('Background Stock Sync') }}</h4>
											<div v-if="stockSyncStatus.enabled" class="ms-auto flex items-center px-2.5 py-1 bg-green-100 border border-green-300 rounded-full">
												<div class="w-2 h-2 bg-green-500 rounded-full animate-pulse me-2"></div>
												<span class="text-xs font-medium text-green-800">{{ __('Active') }}</span>
											</div>
											<div v-else class="ms-auto flex items-center px-2.5 py-1 bg-gray-100 border border-gray-300 rounded-full">
												<div class="w-2 h-2 bg-gray-400 rounded-full me-2"></div>
												<span class="text-xs font-medium text-gray-600">{{ __('Inactive') }}</span>
											</div>
										</div>

										<div class="flex flex-col gap-4">
											<!-- Enable Sync Toggle -->
											<CheckboxField
												v-model="stockSyncEnabled"
												:label="__('Enable Automatic Stock Sync')"
												:description="__('Periodically sync stock quantities from server in the background (runs in Web Worker)')"
											/>

											<!-- Sync Interval -->
											<div v-if="stockSyncEnabled" class="ps-6 flex flex-col gap-3 border-s-2 border-blue-200">
												<NumberField
													v-model="stockSyncIntervalSeconds"
													:label="__('Sync Interval (seconds)')"
													:description="__('How often to check server for stock updates (minimum 10 seconds)')"
													:min="10"
													:max="300"
													:step="10"
												/>

												<!-- Sync Status Info -->
												<div class="p-3 bg-blue-50 border border-blue-200 rounded-lg">
													<div class="flex items-start gap-2">
														<svg class="w-4 h-4 text-blue-600 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
															<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="icons.info"/>
														</svg>
														<div class="text-xs text-blue-800 flex flex-col gap-1">
															<TranslatedHTML 
																:tag="'p'"
																:inner="stockSyncStatus.enabled 
																	? __('&lt;strong&gt;Status:&lt;strong&gt; Running')
																	: __('&lt;strong&gt;Status:&lt;strong&gt; Stopped')"
															/>
															<TranslatedHTML
																:tag="'p'"
																:inner="__('&lt;strong&gt;Items Tracked:&lt;strong&gt; {0}', [stockSyncStatus.itemCount || 0])"
															/>
															<TranslatedHTML 
																:tag="'p'"
																:inner="stockSyncStatus.warehouse
																	? __('&lt;strong&gt;Warehouse:&lt;strong&gt; {0}', [stockSyncStatus.warehouse])
																	: __('Warehouse not set')"
															/>
															<TranslatedHTML 
																:tag="'p'"
																:inner="stockSyncStatus.lastSync
																	? __('&lt;strong&gt;Last Sync:&lt;strong&gt; {0}', [formatSyncTime(stockSyncStatus.lastSync)]) 
																	: __('&lt;strong&gt;Last Sync:&lt;strong&gt; Never')"
															/>
														</div>
													</div>
												</div>

												<!-- Network Usage Info -->
												<div class="p-3 bg-gray-50 border border-gray-200 rounded-lg">
													<div class="flex items-start gap-2">
														<svg class="w-4 h-4 text-gray-600 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
															<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
														</svg>
														<div class="text-xs text-gray-700">
															<p class="font-medium mb-1">{{ __('Network Usage:') }}</p>
															<p>{{ __('~15 KB per sync cycle') }}</p>
															<p>{{ __('~{0} MB per hour', [Math.round((3600 / stockSyncIntervalSeconds) * 15 / 1024)]) }}</p>
														</div>
													</div>
												</div>
											</div>
										</div>
									</div>
								</div>
							</div>

							<!-- Sales Management Section - Prominent -->
							<div v-if="activeTab === 'sales'" class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
								<div :class="salesSectionClasses.header">
									<div class="flex items-center justify-between">
										<div class="flex items-center gap-3">
											<div :class="salesSectionClasses.iconContainer">
												<svg :class="salesSectionClasses.icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="icons.shoppingCart"/>
												</svg>
											</div>
											<div>
												<h3 class="text-lg font-bold text-gray-900">{{ __('Sales Management') }}</h3>
												<p class="text-xs text-gray-600 mt-0.5">{{ __('Configure pricing, discounts, and sales operations') }}</p>
											</div>
										</div>
										<div :class="salesSectionClasses.badge">
											<svg :class="salesSectionClasses.badgeIcon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="icons.currency"/>
											</svg>
											<span :class="salesSectionClasses.badgeText">{{ __('Sales Controls') }}</span>
										</div>
									</div>
								</div>
								<div class="p-6 flex flex-col gap-6">
									<!-- Pricing & Discounts -->
									<div :class="pricingSubsectionClasses.container">
										<div class="flex items-center gap-2 mb-4">
											<svg :class="pricingSubsectionClasses.icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="icons.tag"/>
											</svg>
											<h4 class="text-sm font-semibold text-gray-900">{{ __('Pricing & Discounts') }}</h4>
										</div>
										<div class="flex flex-col gap-3">
											<CheckboxField
												v-model="settings.tax_inclusive"
												:label="__('Tax Inclusive')"
												:description="__('When enabled, displayed prices include tax. When disabled, tax is calculated separately. Changes apply immediately to your cart when you save.')"
											/>
											<CheckboxField
												v-model="settings.block_zero_price_sales"
												:label="__('Block Zero Price Sales')"
												:description="__('Prevent selling items when the selling price is 0.00 or has not been set.')"
											/>
											<div class="grid gap-3 md:grid-cols-2">
												<label class="block">
													<span class="mb-1 block text-xs font-medium text-gray-700">
														{{ __('Retail Price List') }}
													</span>
													<Autocomplete
														v-model="settings.retail_price_list"
														:options="priceListOptions"
														:loading="loadingPriceLists"
														@search="searchPriceLists"
														@select="(option) => settings.retail_price_list = option.value"
														:allow-custom-value="false"
													/>
													<span class="mt-1 block text-[11px] text-gray-500">
														{{ __('Used by the Retail button. If empty, POS Profile price list is used.') }}
													</span>
												</label>
												<label class="block">
													<span class="mb-1 block text-xs font-medium text-gray-700">
														{{ __('Wholesale Price List') }}
													</span>
													<Autocomplete
														v-model="settings.wholesale_price_list"
														:options="priceListOptions"
														:loading="loadingPriceLists"
														@search="searchPriceLists"
														@select="(option) => settings.wholesale_price_list = option.value"
														:allow-custom-value="false"
													/>
													<span class="mt-1 block text-[11px] text-gray-500">
														{{ __('Used by the Wholesale button on the item screen.') }}
													</span>
												</label>
											</div>
											<NumberField
												v-model="settings.max_discount_allowed"
												:label="__('Max Discount (%)')"
												:description="__('Maximum discount per item')"
												:min="0"
												:max="100"
											/>
											<CheckboxField
												v-model="settings.use_percentage_discount"
												:label="__('Use Percentage Discount')"
												:description="__('Show discounts as percentages')"
											/>
											<CheckboxField
												v-model="settings.allow_user_to_edit_additional_discount"
												:label="__('Allow Additional Discount')"
												:description="__('Enable invoice-level discount')"
											/>
											<CheckboxField
												v-model="settings.allow_user_to_edit_item_discount"
												:label="__('Allow Item Discount')"
												:description="__('Enable item-level discount in edit dialog')"
											/>
											<CheckboxField
												v-model="settings.allow_user_to_edit_rate"
												:label="__('Allow User to Edit Rate')"
												:description="__('Allow cashiers to change the item rate in the edit dialog')"
											/>
											<CheckboxField
												v-model="settings.allow_change_uom"
												:label="__('Allow Change of UOM')"
												:description="__('Allow cashiers to change item units directly from the cart')"
											/>
											<CheckboxField
												v-model="settings.disable_rounded_total"
												:label="__('Disable Rounded Total')"
												:description="__('Show exact totals without rounding')"
											/>
										</div>
									</div>

									<!-- Sales Operations -->
									<div :class="operationsSubsectionClasses.container">
										<div class="flex items-center gap-2 mb-4">
											<svg :class="operationsSubsectionClasses.icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="icons.checkCircle"/>
											</svg>
											<h4 class="text-sm font-semibold text-gray-900">{{ __('Sales Operations') }}</h4>
										</div>
										<div class="flex flex-col gap-3">
											<CheckboxField
												v-model="settings.allow_credit_sale"
												:label="__('Allow Credit Sale')"
												:description="__('Enable Pay on Account. Leave the user list empty to allow all POS users for this profile.')"
											/>
											<div
												v-if="settings.allow_credit_sale"
												class="rounded-lg border border-amber-200 bg-amber-50 p-3"
											>
												<div class="mb-3 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
													<div>
														<h5 class="text-sm font-semibold text-amber-950">
															{{ __('Credit Sale Users') }}
														</h5>
														<p class="mt-1 text-xs text-amber-800">
															{{ __('If this list is empty, all POS users assigned to this profile can sell on credit. Add users to restrict Pay on Account.') }}
														</p>
													</div>
													<button
														type="button"
														class="rounded border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-800 hover:bg-amber-100"
														@click="addCreditSaleUser"
													>
														{{ __('Add User') }}
													</button>
												</div>
												<div v-if="!settings.credit_sale_users?.length" class="rounded border border-dashed border-amber-200 bg-white p-3 text-xs text-gray-500">
													{{ __('No users selected. Credit sale is allowed for all POS users on this profile.') }}
												</div>
												<div v-else class="flex flex-col gap-2">
													<div
														v-for="(row, index) in settings.credit_sale_users"
														:key="index"
														class="grid gap-2 rounded border border-amber-100 bg-white p-2 md:grid-cols-[80px_1fr_auto]"
													>
														<label class="flex items-center gap-2 text-xs text-gray-700">
															<input
																v-model="row.enabled"
																type="checkbox"
																class="h-4 w-4 accent-amber-600"
															/>
															{{ __('On') }}
														</label>
														<label class="block">
															<span class="mb-1 block text-[11px] font-medium text-gray-600">
																{{ __('Allowed User') }}
															</span>
															<Autocomplete
																v-model="row.user"
																:options="userOptions"
																:loading="loadingUsers"
																@search="searchUsers"
																@select="(option) => row.user = option.value"
																:allow-custom-value="false"
															/>
														</label>
														<button
															type="button"
															class="self-end rounded border border-red-200 bg-white px-2.5 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50"
															@click="removeCreditSaleUser(index)"
														>
															{{ __('Remove') }}
														</button>
													</div>
												</div>
											</div>
											<CheckboxField
												v-model="settings.allow_return"
												:label="__('Allow Return')"
												:description="__('Enable product returns')"
											/>
											<CheckboxField
												v-model="settings.allow_write_off_change"
												:label="__('Allow Write Off Change')"
												:description="__('Write off small change amounts')"
											/>
											<CheckboxField
												v-model="settings.allow_partial_payment"
												:label="__('Allow Partial Payment')"
												:description="__('Enable partial payment for invoices')"
											/>
											<SelectField
												v-model="settings.sms_payment_reconciliation_mode"
												:label="__('SMS Payment Reconciliation')"
												:description="__('Per POS Profile: Manual requires cashier selection. Suggested shows likely matches. Auto applies one high-confidence exact match only.')"
												:options="smsReconciliationModeOptions"
											/>
											<CheckboxField
												v-model="settings.global_sms_enabler_enabled"
												:label="__('Use Global SMS Enabler')"
												:description="__('When enabled, all POS Profiles share the global SMS inbox. Disable it to use a separate token and payment inbox for each POS Profile.')"
											/>
											<CheckboxField
												v-if="!settings.global_sms_enabler_enabled"
												v-model="settings.sms_enabler_enabled"
												:label="__('Enable SMS Enabler for this POS Profile')"
												:description="__('Only payments received with this profile token will be visible to this POS Profile.')"
											/>
											<div
												v-if="settings.sms_enabler_enabled"
												class="rounded-lg border border-emerald-200 bg-emerald-50 p-4"
											>
												<div class="mb-3 flex items-start justify-between gap-3">
													<div>
														<h5 class="text-sm font-semibold text-emerald-950">
															{{ settings.sms_enabler_is_global ? __('Global SMS Enabler Webhook') : __('POS Profile SMS Enabler Webhook') }}
														</h5>
														<p class="mt-1 text-xs leading-relaxed text-emerald-800">
															{{ settings.sms_enabler_is_global
																? __('This token receives shared SMS payments for all POS Profiles.')
																: __('Use this token in SMS Enabler Tag. Incoming payments will belong only to this POS Profile.') }}
														</p>
													</div>
													<button
														type="button"
														class="rounded border border-emerald-300 bg-white px-3 py-1.5 text-xs font-medium text-emerald-800 hover:bg-emerald-100 disabled:opacity-60"
														:disabled="regeneratingSmsToken || smsModeChanged"
														@click="regenerateSmsEnablerToken"
													>
														{{ smsModeChanged
															? __('Save Mode First')
															: (regeneratingSmsToken
																? __('Generating...')
																: (settings.sms_enabler_is_global ? __('Regenerate Global Token') : __('Regenerate Profile Token'))) }}
													</button>
												</div>
												<div class="grid gap-3 md:grid-cols-2">
													<label class="block">
														<span class="mb-1 block text-xs font-medium text-gray-700">
															{{ __('Source Label') }}
														</span>
														<input
															v-model="settings.sms_enabler_source"
															type="text"
															class="w-full rounded border border-gray-300 bg-white px-2.5 py-1.5 text-sm focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
															:placeholder="__('SMS Enabler')"
														/>
													</label>
													<label class="block">
														<span class="mb-1 block text-xs font-medium text-gray-700">
															{{ __('Tag / Webhook Token') }}
														</span>
														<input
															:value="settings.sms_enabler_token || __('Generated after save')"
															type="text"
															readonly
															class="w-full rounded border border-gray-300 bg-gray-50 px-2.5 py-1.5 text-sm text-gray-700"
														/>
													</label>
												</div>
												<label class="mt-3 block">
													<span class="mb-1 block text-xs font-medium text-gray-700">
														{{ __('Webhook URL') }}
													</span>
													<textarea
														:value="smsEnablerWebhookUrl"
														readonly
														rows="2"
														class="w-full resize-none rounded border border-gray-300 bg-white px-2.5 py-1.5 text-xs text-gray-700 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
													/>
												</label>
												<div class="mt-2 flex flex-wrap items-center gap-2">
													<button
														type="button"
														class="rounded bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-60"
														:disabled="!smsEnablerWebhookUrl"
														@click="copySmsEnablerWebhookUrl"
													>
														{{ __('Copy Webhook URL') }}
													</button>
													<p class="text-xs text-emerald-800">
														{{ __('SMS Enabler should POST sender, text, scts, and tag fields. Use the token as the tag value.') }}
													</p>
												</div>
												<div class="mt-4 rounded border border-emerald-200 bg-white p-3">
													<div class="mb-3 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
														<div>
															<h6 class="text-xs font-semibold uppercase tracking-wide text-emerald-900">
																{{ __('Bank Sender Mapping') }}
															</h6>
															<p class="mt-1 text-xs text-emerald-800">
																{{ __('Match incoming SMS sender text to the Mode of Payment that should receive the Payment Entry.') }}
															</p>
														</div>
														<button
															type="button"
															class="rounded border border-emerald-300 px-3 py-1.5 text-xs font-medium text-emerald-800 hover:bg-emerald-50"
															@click="addSmsSenderMapping"
														>
															{{ __('Add Mapping') }}
														</button>
													</div>
													<div v-if="!settings.sms_enabler_sender_mappings?.length" class="rounded border border-dashed border-emerald-200 p-3 text-xs text-gray-500">
														{{ __('Add mappings like NCBA_BANK -> NCBA Paybill, Equity Bank -> Equity Paybill, IANDMBANK -> I&M Paybill.') }}
													</div>
													<div v-else class="flex flex-col gap-2">
														<div
															v-for="(mapping, index) in settings.sms_enabler_sender_mappings"
															:key="index"
															class="grid gap-2 rounded border border-gray-200 bg-gray-50 p-2 md:grid-cols-[80px_1fr_1fr_auto]"
														>
															<label class="flex items-center gap-2 text-xs text-gray-700">
																<input
																	v-model="mapping.enabled"
																	type="checkbox"
																	class="h-4 w-4 accent-emerald-600"
																/>
																{{ __('On') }}
															</label>
															<label class="block">
																<span class="mb-1 block text-[11px] font-medium text-gray-600">
																	{{ __('Sender Contains') }}
																</span>
																<input
																	v-model="mapping.match_text"
																	type="text"
																	class="w-full rounded border border-gray-300 bg-white px-2.5 py-1.5 text-sm focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
																	:placeholder="__('NCBA_BANK')"
																/>
															</label>
															<label class="block">
																<span class="mb-1 block text-[11px] font-medium text-gray-600">
																	{{ __('Mode of Payment') }}
																</span>
																<Autocomplete
																	v-model="mapping.mode_of_payment"
																	:options="modeOfPaymentOptions"
																	:loading="loadingModeOfPayments"
																	@search="searchModeOfPayments"
																	@select="(option) => mapping.mode_of_payment = option.value"
																	:allow-custom-value="false"
																/>
															</label>
															<button
																type="button"
																class="self-end rounded border border-red-200 bg-white px-2.5 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50"
																@click="removeSmsSenderMapping(index)"
															>
																{{ __('Remove') }}
															</button>
														</div>
													</div>
												</div>
											</div>
											<CheckboxField
												v-model="settings.silent_print"
												:label="__('Silent Print')"
												:description="__('Print without confirmation')"
											/>
										</div>
									</div>
								</div>
							</div>

							<!-- Customer Settings Section -->
							<div v-if="activeTab === 'customer'" class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
								<div :class="customerSectionClasses.header">
									<div class="flex items-center justify-between">
										<div class="flex items-center gap-3">
											<div :class="customerSectionClasses.iconContainer">
												<svg :class="customerSectionClasses.icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a4 4 0 00-4-4h-1M9 20H4v-2a4 4 0 014-4h1m0-4a4 4 0 100-8 4 4 0 000 8zm8 0a4 4 0 100-8 4 4 0 000 8z"/>
												</svg>
											</div>
											<div>
												<h3 class="text-lg font-bold text-gray-900">{{ __('Customer Settings') }}</h3>
												<p class="text-xs text-gray-600 mt-0.5">{{ __('Set the customer selected automatically when this POS Profile opens') }}</p>
											</div>
										</div>
										<div :class="customerSectionClasses.badge">
											<svg :class="customerSectionClasses.badgeIcon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="icons.checkCircle"/>
											</svg>
											<span :class="customerSectionClasses.badgeText">{{ __('Default Customer') }}</span>
										</div>
									</div>
								</div>
								<div class="p-6 flex flex-col gap-6">
									<div :class="customerSubsectionClasses.container">
										<div class="flex items-center gap-2 mb-4">
											<svg :class="customerSubsectionClasses.icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="icons.info"/>
											</svg>
											<h4 class="text-sm font-semibold text-gray-900">{{ __('Default Sale Customer') }}</h4>
										</div>
										<label class="block">
											<span class="mb-1 block text-xs font-medium text-gray-700">
												{{ __('Default Customer') }}
											</span>
											<Autocomplete
												v-model="defaultCustomer"
												:options="customerOptions"
												:loading="loadingCustomers"
												@search="searchCustomers"
												@select="selectDefaultCustomer"
												:allow-custom-value="false"
											/>
											<span class="mt-1 block text-[11px] text-gray-500">
												{{ __('This customer is preselected for new sales. Cashiers can still change or remove the customer during the sale.') }}
											</span>
										</label>
										<div v-if="defaultCustomer" class="mt-3 flex items-center justify-between rounded border border-blue-100 bg-white p-3">
											<div class="text-xs text-gray-600">
												<span class="font-medium text-gray-900">{{ defaultCustomerLabel }}</span>
											</div>
											<button
												type="button"
												class="rounded border border-gray-200 bg-white px-2.5 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
												@click="clearDefaultCustomer"
											>
												{{ __('Clear') }}
											</button>
										</div>
									</div>
								</div>
							</div>

							<!-- Price List Mapping Section -->
							<div v-if="activeTab === 'pricing'" class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
								<div :class="pricingStrategyClasses.header">
									<div class="flex items-center justify-between">
										<div class="flex items-center gap-3">
											<div :class="pricingStrategyClasses.iconContainer">
												<svg :class="pricingStrategyClasses.icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
												</svg>
											</div>
											<div>
												<h3 class="text-lg font-bold text-gray-900">{{ __('Conditional Pricing') }}</h3>
												<p class="text-xs text-gray-600 mt-0.5">{{ __('Apply different price lists based on warehouse and customer group') }}</p>
											</div>
										</div>
										<div :class="pricingStrategyClasses.badge">
											<svg :class="pricingStrategyClasses.badgeIcon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
											</svg>
											<span :class="pricingStrategyClasses.badgeText">{{ __('Pricing Rules') }}</span>
										</div>
									</div>
								</div>
								<div class="p-6">
									<PriceListMapping :pos-profile="props.posProfile" />
								</div>
							</div>
						</div>

						<!-- Empty State -->
						<div v-else class="flex flex-col items-center justify-center py-16 text-center">
							<svg class="w-16 h-16 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
							</svg>
							<p class="text-gray-600 font-medium">{{ __('No POS Profile Selected') }}</p>
							<p class="text-gray-500 text-sm mt-1">{{ __('Please select a POS Profile to configure settings') }}</p>
						</div>
					</div>
				</div>
			</div>
		</div>
	</Transition>
</template>

<script setup>
import CheckboxField from "@/components/settings/CheckboxField.vue"
import NumberField from "@/components/settings/NumberField.vue"
import SelectField from "@/components/settings/SelectField.vue"
import PriceListMapping from "@/components/settings/PriceListMapping.vue"
import { useToast } from "@/composables/useToast"
import { Autocomplete, Button, call, createResource } from "frappe-ui"
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue"
import {
	getSectionHeaderClasses,
	getSubsectionClasses,
	icons,
} from "./settingsConfig"
import { offlineWorker } from "@/utils/offline/workerClient"
import { logger } from "@/utils/logger"
import { usePOSEvents } from "@/composables/usePOSEvents"
import TranslatedHTML from "../common/TranslatedHTML.vue"

const log = logger.create('POSSettings')
const { detectSettingsChanges, updateSettingsSnapshot, emitStockSyncConfigured } = usePOSEvents()
const { showSuccess, showError } = useToast()

const props = defineProps({
	modelValue: Boolean,
	posProfile: String,
	currentWarehouse: String,
})

const emit = defineEmits([
	"update:modelValue",
	"warehouse-changed",
	"default-customer-changed",
])

const show = ref(props.modelValue)

// State
const activeTab = ref('stock')
const loading = ref(true)
const saving = ref(false)
const warehousesList = ref([])
const selectedWarehouse = ref(props.currentWarehouse || "")
const settings = ref({
	pos_profile: props.posProfile || "",
	enabled: 1,
	// Core Settings
	max_discount_allowed: 0,
	use_percentage_discount: 0,
	allow_user_to_edit_additional_discount: 0,
	allow_user_to_edit_item_discount: 1,
	allow_user_to_edit_rate: 0,
	allow_change_uom: 0,
	disable_rounded_total: 1,
	allow_credit_sale: 0,
	credit_sale_users: [],
	allow_return: 0,
	allow_write_off_change: 0,
	allow_partial_payment: 0,
	sms_payment_reconciliation_mode: "Manual",
	sms_enabler_enabled: 0,
	sms_enabler_source: "SMS Enabler",
	sms_enabler_token: "",
	sms_enabler_webhook_url: "",
	sms_enabler_is_global: 1,
	sms_enabler_sender_mappings: [],
	global_sms_enabler_enabled: 0,
	global_sms_enabler_source: "SMS Enabler",
	global_sms_enabler_token: "",
	global_sms_enabler_sender_mappings: [],
	profile_sms_enabler_enabled: 0,
	profile_sms_enabler_source: "SMS Enabler",
	profile_sms_enabler_token: "",
	profile_sms_enabler_sender_mappings: [],
	silent_print: 0,
	allow_negative_stock: 0,
	tax_inclusive: 0,
	block_zero_price_sales: 0,
	retail_price_list: "",
	wholesale_price_list: "",
})
const regeneratingSmsToken = ref(false)
const smsModeReady = ref(false)
const savedGlobalSmsMode = ref(false)
const smsModeChanged = computed(
	() => Boolean(settings.value.global_sms_enabler_enabled) !== savedGlobalSmsMode.value,
)
const priceListOptions = ref([])
const loadingPriceLists = ref(false)
const modeOfPaymentOptions = ref([])
const loadingModeOfPayments = ref(false)
const userOptions = ref([])
const loadingUsers = ref(false)
const defaultCustomer = ref("")
const defaultCustomerLabel = ref("")
const originalDefaultCustomer = ref("")
const customerOptions = ref([])
const loadingCustomers = ref(false)

// Stock Sync Settings (localStorage persisted)
const stockSyncEnabled = ref(false)
const stockSyncIntervalSeconds = ref(60) // Default 60 seconds
const stockSyncStatus = ref({
	enabled: false,
	warehouse: null,
	itemCount: 0,
	intervalMs: 60000,
	lastSync: null,
	running: false
})

// Warehouse options
const warehouseOptions = computed(() => {
	if (warehousesList.value.length === 0) return []
	return warehousesList.value.map((w) => ({
		label: w.warehouse_name || w.name,
		value: w.name,
	}))
})

// Dynamic classes using configuration helpers (DRY principle)
const stockSectionClasses = computed(() => getSectionHeaderClasses("purple"))
const salesSectionClasses = computed(() => getSectionHeaderClasses("green"))
const customerSectionClasses = computed(() => getSectionHeaderClasses("blue"))
const pricingStrategyClasses = computed(() => getSectionHeaderClasses("amber"))
const warehouseSubsectionClasses = computed(() => getSubsectionClasses("gray"))
const stockPolicySubsectionClasses = computed(() =>
	getSubsectionClasses("blue"),
)
const stockSyncSubsectionClasses = computed(() => getSubsectionClasses("indigo"))
const pricingSubsectionClasses = computed(() => getSubsectionClasses("emerald"))
const operationsSubsectionClasses = computed(() => getSubsectionClasses("teal"))
const customerSubsectionClasses = computed(() => getSubsectionClasses("blue"))
const smsReconciliationModeOptions = computed(() => [
	{ label: __("Manual"), value: "Manual" },
	{ label: __("Suggested"), value: "Suggested" },
	{ label: __("Auto"), value: "Auto" },
])
const smsEnablerWebhookUrl = computed(() => {
	if (settings.value.sms_enabler_webhook_url) {
		return settings.value.sms_enabler_webhook_url
	}

	if (settings.value.sms_enabler_token && typeof window !== "undefined") {
		return `${window.location.origin}/api/method/pos_next.api.smsenabler_mpesa.receive_sms`
	}

	return ""
})

// Resources
const warehousesResource = createResource({
	url: "pos_next.api.pos_profile.get_warehouses",
	makeParams() {
		return {
			pos_profile: props.posProfile,
		}
	},
	auto: false,
	onSuccess(data) {
		const warehouses = data?.message || data || []
		warehousesList.value = warehouses
	},
	onError(error) {
		warehousesList.value = []
	},
})

// Track original allow_negative_stock value for detecting changes
const originalAllowNegativeStock = ref(null)

const settingsResource = createResource({
	url: "pos_next.pos_next.doctype.pos_settings.pos_settings.get_pos_settings",
	makeParams() {
		return {
			pos_profile: props.posProfile,
		}
	},
	onSuccess(data) {
		if (data) {
			smsModeReady.value = false
			Object.assign(settings.value, data)
			savedGlobalSmsMode.value = Boolean(data.global_sms_enabler_enabled)
			settings.value.pos_profile = props.posProfile
			normalizeSmsSenderMappings()
			normalizeCreditSaleUsers()
			// Store original value
			originalAllowNegativeStock.value = data.allow_negative_stock
			// Update event system snapshot
			updateSettingsSnapshot(settings.value)
			nextTick(() => {
				smsModeReady.value = true
			})
		}
		loading.value = false
	},
	onError(error) {
		loading.value = false
		showError(__("Failed to load settings"))
	},
})

// Watchers
watch(
	() => props.modelValue,
	(val) => {
		show.value = val
		if (val) {
			loadSettings()
		}
	},
)

watch(show, (val) => {
	emit("update:modelValue", val)
})

watch(
	() => settings.value.global_sms_enabler_enabled,
	(newValue, oldValue) => {
		if (!smsModeReady.value || Boolean(newValue) === Boolean(oldValue)) return

		const oldPrefix = oldValue ? "global" : "profile"
		settings.value[`${oldPrefix}_sms_enabler_enabled`] = settings.value.sms_enabler_enabled
		settings.value[`${oldPrefix}_sms_enabler_source`] = settings.value.sms_enabler_source
		settings.value[`${oldPrefix}_sms_enabler_token`] = settings.value.sms_enabler_token
		settings.value[`${oldPrefix}_sms_enabler_sender_mappings`] = cloneSmsSenderMappings(
			settings.value.sms_enabler_sender_mappings || [],
		)

		const newPrefix = newValue ? "global" : "profile"
		settings.value.sms_enabler_enabled = newValue
			? 1
			: settings.value[`${newPrefix}_sms_enabler_enabled`] || 0
		settings.value.sms_enabler_source =
			settings.value[`${newPrefix}_sms_enabler_source`] || "SMS Enabler"
		settings.value.sms_enabler_token =
			settings.value[`${newPrefix}_sms_enabler_token`] || ""
		settings.value.sms_enabler_sender_mappings = cloneSmsSenderMappings(
			settings.value[`${newPrefix}_sms_enabler_sender_mappings`] || [],
		)
		settings.value.sms_enabler_is_global = newValue ? 1 : 0
	},
)

// Watch for currentWarehouse prop changes and always sync
watch(
	() => props.currentWarehouse,
	(newWarehouse) => {
		if (newWarehouse) {
			selectedWarehouse.value = newWarehouse
		}
	},
	{ immediate: true },
)

// Watch for tax_inclusive changes to provide immediate feedback
const originalTaxInclusive = ref(null)
watch(
	() => settings.value.tax_inclusive,
	(newValue, oldValue) => {
		// Store original value on first load
		if (originalTaxInclusive.value === null && oldValue !== undefined) {
			originalTaxInclusive.value = oldValue
		}

		// Only show feedback if value actually changed from original
		if (originalTaxInclusive.value !== null && newValue !== originalTaxInclusive.value) {
			const mode = newValue ? 'inclusive' : 'exclusive'
			log.info(`Tax mode toggled to: ${mode}`)
		}
	}
)

// Methods
function handleClose() {
	show.value = false
}

async function copySmsEnablerWebhookUrl() {
	if (!smsEnablerWebhookUrl.value) return

	try {
		await navigator.clipboard.writeText(smsEnablerWebhookUrl.value)
		showSuccess(__("SMS Enabler webhook URL copied"))
	} catch (error) {
		log.error("Failed to copy SMS Enabler webhook URL:", error)
		showError(__("Could not copy webhook URL"))
	}
}

async function regenerateSmsEnablerToken() {
	regeneratingSmsToken.value = true
	try {
		const result = await call(
			"pos_next.pos_next.doctype.pos_settings.pos_settings.regenerate_sms_enabler_token",
			{
				pos_profile: props.posProfile,
			},
		)
		settings.value.sms_enabler_enabled = 1
		settings.value.sms_enabler_token = result?.token || ""
		settings.value.sms_enabler_webhook_url = result?.webhook_url || ""
		settings.value.sms_enabler_is_global = result?.sms_enabler_is_global ? 1 : 0
		showSuccess(
			settings.value.sms_enabler_is_global
				? __("Global SMS Enabler token regenerated")
				: __("POS Profile SMS Enabler token regenerated"),
		)
	} catch (error) {
		log.error("Failed to regenerate SMS Enabler token:", error)
		showError(error.message || __("Could not regenerate SMS Enabler token"))
	} finally {
		regeneratingSmsToken.value = false
	}
}

async function searchPriceLists(query = "") {
	loadingPriceLists.value = true
	try {
		const result = await call("frappe.client.get_list", {
			doctype: "Price List",
			fields: ["name"],
			filters: {
				name: ["like", `%${query || ""}%`],
				enabled: 1,
			},
			limit_page_length: 20,
		})

		priceListOptions.value = (result?.message || result || []).map((row) => ({
			label: row.name,
			value: row.name,
		}))
	} catch (error) {
		log.error("Failed to search price lists:", error)
		priceListOptions.value = []
	} finally {
		loadingPriceLists.value = false
	}
}

async function searchModeOfPayments(query = "") {
	loadingModeOfPayments.value = true
	try {
		const filters = {
			enabled: 1,
			name: ["like", `%${query || ""}%`],
		}
		const result = await call("frappe.client.get_list", {
			doctype: "Mode of Payment",
			fields: ["name", "type"],
			filters,
			limit_page_length: 20,
		})

		modeOfPaymentOptions.value = (result?.message || result || []).map((row) => ({
			label: row.type ? `${row.name} (${row.type})` : row.name,
			value: row.name,
		}))
	} catch (error) {
		log.error("Failed to search modes of payment:", error)
		modeOfPaymentOptions.value = []
	} finally {
		loadingModeOfPayments.value = false
	}
}

async function searchUsers(query = "") {
	loadingUsers.value = true
	try {
		const result = await call("frappe.client.get_list", {
			doctype: "User",
			fields: ["name", "full_name"],
			filters: { enabled: 1 },
			or_filters: [
				["name", "like", `%${query || ""}%`],
				["full_name", "like", `%${query || ""}%`],
			],
			limit_page_length: 20,
		})

		userOptions.value = (result?.message || result || []).map((row) => ({
			label: row.full_name ? `${row.full_name} (${row.name})` : row.name,
			value: row.name,
		}))
	} catch (error) {
		log.error("Failed to search users:", error)
		userOptions.value = []
	} finally {
		loadingUsers.value = false
	}
}

async function searchCustomers(query = "") {
	loadingCustomers.value = true
	try {
		const result = await call("pos_next.api.customers.get_customers", {
			search_term: query || "",
			pos_profile: props.posProfile,
			limit: 20,
		})

		customerOptions.value = (result?.message || result || []).map((row) => ({
			label: row.customer_name ? `${row.customer_name} (${row.name})` : row.name,
			value: row.name,
		}))
	} catch (error) {
		log.error("Failed to search customers:", error)
		customerOptions.value = []
	} finally {
		loadingCustomers.value = false
	}
}

function clearDefaultCustomer() {
	defaultCustomer.value = ""
	defaultCustomerLabel.value = ""
}

function selectDefaultCustomer(option) {
	defaultCustomer.value = option?.value || ""
	defaultCustomerLabel.value = option?.label || defaultCustomer.value
}

async function loadDefaultCustomer() {
	try {
		const result = await call("pos_next.api.pos_profile.get_default_customer", {
			pos_profile: props.posProfile,
		})

		defaultCustomer.value = result?.customer || ""
		defaultCustomerLabel.value = result?.customer
			? `${result.customer_name || result.customer} (${result.customer})`
			: ""
		originalDefaultCustomer.value = defaultCustomer.value

		if (defaultCustomer.value) {
			customerOptions.value = [
				{
					label: defaultCustomerLabel.value,
					value: defaultCustomer.value,
				},
			]
		}
	} catch (error) {
		log.error("Failed to load default customer:", error)
		clearDefaultCustomer()
		originalDefaultCustomer.value = ""
	}
}

function normalizeCreditSaleUsers() {
	if (!Array.isArray(settings.value.credit_sale_users)) {
		settings.value.credit_sale_users = []
		return
	}

	settings.value.credit_sale_users = settings.value.credit_sale_users.map((row) => ({
		enabled: row.enabled ?? 1,
		user: row.user || "",
		full_name: row.full_name || "",
	}))
}

function addCreditSaleUser() {
	normalizeCreditSaleUsers()
	settings.value.credit_sale_users.push({
		enabled: 1,
		user: "",
		full_name: "",
	})
}

function removeCreditSaleUser(index) {
	settings.value.credit_sale_users.splice(index, 1)
}

function normalizeSmsSenderMappings() {
	if (!Array.isArray(settings.value.sms_enabler_sender_mappings)) {
		settings.value.sms_enabler_sender_mappings = []
		return
	}

	settings.value.sms_enabler_sender_mappings = settings.value.sms_enabler_sender_mappings.map((mapping) => ({
		enabled: mapping.enabled ?? 1,
		match_text: mapping.match_text || "",
		mode_of_payment: mapping.mode_of_payment || "",
	}))
}

function cloneSmsSenderMappings(mappings) {
	return (mappings || []).map((mapping) => ({ ...mapping }))
}

function addSmsSenderMapping() {
	normalizeSmsSenderMappings()
	settings.value.sms_enabler_sender_mappings.push({
		enabled: 1,
		match_text: "",
		mode_of_payment: "",
	})
}

function removeSmsSenderMapping(index) {
	settings.value.sms_enabler_sender_mappings.splice(index, 1)
}

async function loadSettings() {
	if (!props.posProfile) return
	loading.value = true
	settings.value.pos_profile = props.posProfile

	// Always set the current warehouse from props (from current shift/profile)
	selectedWarehouse.value = props.currentWarehouse || ""

	try {
		// Load warehouses first using call API directly
		const warehousesData = await call(
			"pos_next.api.pos_profile.get_warehouses",
			{
				pos_profile: props.posProfile,
			},
		)

		// Handle frappe-ui call response format { message: [...] }
		warehousesList.value = warehousesData?.message || warehousesData || []

		await loadDefaultCustomer()

		// Load settings
		settingsResource.reload()
	} catch (error) {
		log.error("Error loading warehouses:", error)
		warehousesList.value = []
		await loadDefaultCustomer()
		// Still load settings even if warehouses fail
		settingsResource.reload()
	}
}

async function saveSettings() {
	if (!props.posProfile) {
		showError(__("POS Profile not found"))
		return
	}

	saving.value = true
	const oldWarehouse = props.currentWarehouse
	const warehouseChanged = selectedWarehouse.value !== oldWarehouse
	const defaultCustomerChanged = defaultCustomer.value !== originalDefaultCustomer.value
	const negativeStockChanged = originalAllowNegativeStock.value !== settings.value.allow_negative_stock
	const taxInclusiveChanged = originalTaxInclusive.value !== null && originalTaxInclusive.value !== settings.value.tax_inclusive

	// Capture old settings for change detection
	const oldSettings = {
		...settings.value,
		warehouse: oldWarehouse // Include warehouse in change detection
	}

	try {
		// Save POS Settings (without warehouse)
		const result = await call(
			"pos_next.pos_next.doctype.pos_settings.pos_settings.update_pos_settings",
			{
				pos_profile: props.posProfile,
				settings: settings.value,
			},
		)

		if (result) {
			smsModeReady.value = false
			Object.assign(settings.value, result)
			savedGlobalSmsMode.value = Boolean(result.global_sms_enabler_enabled)
			settings.value.pos_profile = props.posProfile
			normalizeSmsSenderMappings()
			normalizeCreditSaleUsers()
			// Update original values after successful save
			originalAllowNegativeStock.value = result.allow_negative_stock
			originalTaxInclusive.value = result.tax_inclusive
			nextTick(() => {
				smsModeReady.value = true
			})
		}

		// Update warehouse in POS Profile if changed
		if (warehouseChanged && selectedWarehouse.value) {
			const warehouseResult = await call(
				"pos_next.api.pos_profile.update_warehouse",
				{
					pos_profile: props.posProfile,
					warehouse: selectedWarehouse.value,
				},
			)

			if (warehouseResult && warehouseResult.success) {
				// Add warehouse to new settings for change detection
				settings.value.warehouse = selectedWarehouse.value

				// Emit event to parent to reload stock with new warehouse
				emit("warehouse-changed", selectedWarehouse.value)
			}
		}

		if (defaultCustomerChanged) {
			const customerResult = await call(
				"pos_next.api.pos_profile.update_default_customer",
				{
					pos_profile: props.posProfile,
					customer: defaultCustomer.value || "",
				},
			)

			originalDefaultCustomer.value = customerResult?.customer || ""
			defaultCustomer.value = customerResult?.customer || ""
			defaultCustomerLabel.value = customerResult?.customer
				? `${customerResult.customer_name || customerResult.customer} (${customerResult.customer})`
				: ""

			emit("default-customer-changed", {
				name: customerResult?.customer || "",
				customer_name: customerResult?.customer_name || customerResult?.customer || "",
				customer_group: customerResult?.customer_group || "",
			})
		}

		// Detect and emit settings changes through event system
		// This will notify all listeners (POSSale, stock store, cart store, etc.)
		detectSettingsChanges(settings.value, oldSettings)

		// IMPORTANT: Page reload for critical stock policy change
		// The allow_negative_stock setting affects deep stock validation logic
		// throughout the app, including:
		// - Stock validation in cart operations (posCart.js:59)
		// - Stock enforcement checks (posSettings.js:268)
		// - Item addition logic and error handling
		// A page reload ensures all components get the fresh setting and
		// prevents inconsistent state. Event listeners are still notified
		// before reload for any cleanup needed.
		if (negativeStockChanged) {
			log.info("Stock policy changed, reloading page for consistency...")
			window.location.reload()
			return
		}

		// Show success toast for other changes
		let successMessage = __("Settings saved successfully")
		if (warehouseChanged && taxInclusiveChanged) {
			successMessage = __("Settings saved, warehouse updated, and tax mode changed. Cart will be recalculated.")
		} else if (warehouseChanged) {
			successMessage = __("Settings saved and warehouse updated. Reloading stock...")
		} else if (taxInclusiveChanged) {
			successMessage = settings.value.tax_inclusive
				? __('Settings saved. Tax mode is now "inclusive". Cart will be recalculated.')
				: __('Settings saved. Tax mode is now "exclusive". Cart will be recalculated.')
		}

		showSuccess(successMessage)
	} catch (error) {
		log.error("Error saving settings:", error)
		showError(error.message || __("Failed to save settings"))
	} finally {
		saving.value = false
	}
}

// ============================================================================
// STOCK SYNC FUNCTIONS
// ============================================================================

// Load stock sync settings from localStorage
function loadStockSyncSettings() {
	try {
		const saved = localStorage.getItem('pos_stock_sync_settings')
		if (saved) {
			const parsed = JSON.parse(saved)
			stockSyncEnabled.value = parsed.enabled ?? false
			stockSyncIntervalSeconds.value = parsed.intervalSeconds ?? 60
		}
	} catch (error) {
		log.error('Failed to load stock sync settings:', error)
	}
}

// Save stock sync settings to localStorage
function saveStockSyncSettings() {
	try {
		localStorage.setItem('pos_stock_sync_settings', JSON.stringify({
			enabled: stockSyncEnabled.value,
			intervalSeconds: stockSyncIntervalSeconds.value
		}))
	} catch (error) {
		log.error('Failed to save stock sync settings:', error)
	}
}

// Update stock sync status
async function updateStockSyncStatus() {
	try {
		const status = await offlineWorker.getStockSyncStatus()
		stockSyncStatus.value = status
	} catch (error) {
		log.error('Failed to get stock sync status:', error)
	}
}

// Apply stock sync configuration to worker
async function applyStockSyncConfig() {
	try {
		const intervalMs = stockSyncIntervalSeconds.value * 1000

		if (stockSyncEnabled.value) {
			// Configure and start sync
			await offlineWorker.configureStockSync({
				intervalMs
			})
			await offlineWorker.startStockSync()
		} else {
			// Stop sync
			await offlineWorker.stopStockSync()
		}

		// Update status
		await updateStockSyncStatus()

		// Save to localStorage
		saveStockSyncSettings()

		// Emit sync configuration change event
		emitStockSyncConfigured({
			enabled: stockSyncEnabled.value,
			intervalMs: intervalMs
		})
	} catch (error) {
		log.error('Failed to apply stock sync config:', error)
	}
}

// Format sync time for display
function formatSyncTime(timestamp) {
	if (!timestamp) return __('Never')

	const now = Date.now()
	const diff = now - timestamp

	if (diff < 60000) {
		return __('{0}s ago', [Math.floor(diff / 1000)])
	} else if (diff < 3600000) {
		return __('{0}m ago', [Math.floor(diff / 60000)])
	} else {
		const date = new Date(timestamp)
		return date.toLocaleTimeString()
	}
}

// Watch for changes and apply
watch(stockSyncEnabled, () => {
	applyStockSyncConfig()
})

watch(stockSyncIntervalSeconds, () => {
	if (stockSyncEnabled.value) {
		applyStockSyncConfig()
	}
})

// Lifecycle hooks
onMounted(async () => {
	// Load settings
	loadStockSyncSettings()
	searchModeOfPayments()
	searchUsers()

	// Update status initially
	await updateStockSyncStatus()

	// Poll status every 5 seconds
	const statusInterval = setInterval(() => {
		updateStockSyncStatus()
	}, 5000)

	// Cleanup on unmount
	onUnmounted(() => {
		clearInterval(statusInterval)
	})
})
</script>

<style scoped>
/* Fade transition for overlay */
.fade-enter-active,
.fade-leave-active {
	transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
	opacity: 0;
}
</style>

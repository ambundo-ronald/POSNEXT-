<template>
	<Dialog v-model="show" :options="{ title: __('Complete Payment'), size: '4xl' }">
		<template #body-content>
			<div class="flex flex-col gap-4">
				<!-- INFORMATION SECTION (TOP) -->

				<!-- Payment Summary Card -->
				<div class="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-4 border border-blue-100">
					<div class="flex justify-between items-start mb-3">
						<div>
							<div class="text-start text-xs font-medium text-gray-600 mb-1">{{ __('Total Amount') }}</div>
							<div class="text-start text-3xl font-bold text-gray-900">
								{{ formatCurrency(grandTotal) }}
							</div>
						</div>
						<div class="text-end">
							<div v-if="remainingAmount > 0" class="mb-2">
								<div class="text-start text-xs font-medium text-orange-600 mb-1">{{ __('Remaining') }}</div>
								<div class="text-start text-xl font-bold text-orange-600">
									{{ formatCurrency(remainingAmount) }}
								</div>
							</div>
							<div v-if="changeAmount > 0">
								<div class="text-start text-xs font-medium text-green-600 mb-1">{{ __('Change') }}</div>
								<div class="text-start text-xl font-bold text-green-600">
									{{ formatCurrency(changeAmount) }}
								</div>
							</div>
							<div v-if="totalPaid >= grandTotal && changeAmount === 0" class="flex items-center text-green-600">
								<svg class="w-5 h-5 me-1" fill="currentColor" viewBox="0 0 20 20">
									<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
								</svg>
								<span class="text-start text-xs font-semibold">{{ __('Paid in Full') }}</span>
							</div>
						</div>
					</div>

					<!-- Progress Bar -->
					<div class="w-full bg-white rounded-full h-2.5 overflow-hidden shadow-inner">
						<div
							:class="[
								'h-full transition-all duration-300',
								totalPaid >= grandTotal ? 'bg-green-500' : 'bg-blue-500'
							]"
							:style="{ width: `${grandTotal > 0 ? Math.min((totalPaid / grandTotal) * 100, 100) : 0}%` }"
						></div>
					</div>
					<div class="text-start text-xs text-gray-600 mt-1">
						{{ __('{0} paid of {1}', [formatCurrency(totalPaid), formatCurrency(grandTotal)]) }}
					</div>
				</div>

				<!-- Customer Credit Display -->
				<div
					v-if="allowCreditSale"
					:class="[
						'rounded-lg p-3 border-2',
						totalAvailableCredit > 0
							? 'bg-gradient-to-br from-emerald-50 to-green-50 border-emerald-200'
							: totalAvailableCredit < 0
							? 'bg-gradient-to-br from-red-50 to-rose-50 border-red-300'
							: 'bg-gradient-to-br from-gray-50 to-slate-50 border-gray-200'
					]"
				>
					<div class="flex items-center justify-between">
						<div class="flex items-center gap-2">
							<div
								:class="[
									'w-8 h-8 rounded-full flex items-center justify-center',
									totalAvailableCredit > 0
										? 'bg-emerald-200'
										: totalAvailableCredit < 0
										? 'bg-red-200'
										: 'bg-gray-200'
								]"
							>
								<svg
									:class="[
										'w-5 h-5',
										totalAvailableCredit > 0
											? 'text-emerald-700'
											: totalAvailableCredit < 0
											? 'text-red-700'
											: 'text-gray-700'
									]"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										v-if="totalAvailableCredit >= 0"
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"
									/>
									<path
										v-else
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
									/>
								</svg>
							</div>
							<div>
								<div class="text-start text-xs font-semibold text-gray-800">
									{{ totalAvailableCredit >= 0 ? __('Customer Credit Available') : __('Customer Outstanding Balance') }}
								</div>
								<div v-if="totalAvailableCredit > 0" class="text-start text-xs text-emerald-700">
									{{ __('Credit can be applied to invoice') }}
								</div>
								<div v-else-if="totalAvailableCredit < 0" class="text-start text-xs text-red-700">
									{{ __('Amount owed by customer') }}
								</div>
								<div v-else class="text-start text-xs text-gray-600">
									{{ __('No outstanding balance') }}
								</div>
							</div>
						</div>
						<div class="text-end">
							<div
								:class="[
									'text-start text-xs font-medium',
									totalAvailableCredit > 0
										? 'text-emerald-700'
										: totalAvailableCredit < 0
										? 'text-red-700'
										: 'text-gray-700'
								]"
							>
								{{ totalAvailableCredit >= 0 ? __('Available') : __('Outstanding') }}
							</div>
							<div
								:class="[
									'text-start text-2xl font-bold',
									totalAvailableCredit > 0
										? 'text-emerald-700'
										: totalAvailableCredit < 0
										? 'text-red-700'
										: 'text-gray-700'
								]"
							>
								{{ formatCurrency(Math.abs(totalAvailableCredit)) }}
							</div>
						</div>
					</div>
				</div>

				<!-- Sales Persons Selection -->
				<div v-if="settingsStore.enableSalesPersons" class="bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200 rounded-lg p-3">
					<div class="flex items-center justify-between mb-2">
						<div class="flex items-center gap-2">
							<div class="w-6 h-6 rounded-full bg-purple-200 flex items-center justify-center">
								<svg class="w-4 h-4 text-purple-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
								</svg>
							</div>
							<span class="text-xs font-bold text-purple-900">
								{{ settingsStore.isMultipleSalesPersons
									? __('Sales Persons')
									: __('Sales Person')
								}}
							</span>
							<span v-if="selectedSalesPersons.length > 0" class="text-xs font-bold text-purple-600 bg-purple-100 px-2 py-0.5 rounded">
								{{ settingsStore.isSingleSalesPerson
									? __('1 selected')
									: __('{0} selected', [selectedSalesPersons.length]) }}
							</span>
						</div>
						<button
							v-if="selectedSalesPersons.length > 0"
							@click="clearSalesPersons"
							class="text-xs text-purple-700 hover:text-purple-900 font-semibold px-2 py-1 bg-purple-100 hover:bg-purple-200 rounded transition-colors"
						>
							{{ settingsStore.isSingleSalesPerson ? __('Clear') : __('Clear All') }}
						</button>
					</div>

					<!-- Search Input -->
					<div class="relative mb-2">
						<input
							v-model="salesPersonSearch"
							type="text"
							:placeholder="__('Search sales person...')"
							class="w-full px-3 py-2 ps-9 text-xs border border-purple-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent bg-white"
						/>
						<svg class="w-4 h-4 text-gray-400 absolute start-3 top-1/2 -translate-y-1/2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
						</svg>
					</div>

					<!-- Selected Sales Persons (Chips) -->
					<div v-if="selectedSalesPersons.length > 0" class="mb-2 flex flex-col gap-1.5">
						<div class="text-[10px] font-semibold text-purple-700 uppercase tracking-wide mb-1">{{ __('Selected:') }}</div>
						<div
							v-for="person in selectedSalesPersons"
							:key="person.sales_person"
							class="flex items-center justify-between p-2 bg-purple-100 border border-purple-300 rounded-lg"
						>
							<div class="flex items-center gap-2 flex-1">
								<button
									@click="removeSalesPerson(person.sales_person)"
									class="text-purple-600 hover:text-purple-800 hover:bg-purple-200 rounded p-0.5 transition-colors"
								>
									<svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
										<path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
									</svg>
								</button>
								<span class="text-xs font-medium text-gray-900 flex-1">
									{{ person.sales_person_name || person.sales_person }}
								</span>
							</div>
							<!-- Only show allocation input for Multiple mode -->
							<div v-if="settingsStore.isMultipleSalesPersons" class="flex items-center gap-1">
								<input
									type="number"
									:value="person.allocated_percentage"
									@input="updateSalesPersonAllocation(person.sales_person, $event.target.value)"
									placeholder="%"
									min="0"
									max="100"
									step="1"
									class="w-14 px-1.5 py-1 text-xs font-semibold text-end border border-purple-300 rounded focus:outline-none focus:ring-1 focus:ring-purple-500 bg-white"
								/>
								<span class="text-xs text-gray-600 font-medium">%</span>
							</div>
							<!-- Show 100% badge for Single mode -->
							<div v-else class="text-xs font-semibold text-purple-700 bg-purple-200 px-2 py-1 rounded">
								100%
							</div>
						</div>

						<!-- Total Allocation Warning (only for Multiple mode) -->
						<div v-if="settingsStore.isMultipleSalesPersons && totalAllocation !== 100" class="flex items-center gap-2 p-2 bg-yellow-50 border border-yellow-300 rounded mt-2">
							<svg class="w-4 h-4 text-yellow-600 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
								<path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
							</svg>
							<span class="text-xs font-medium text-yellow-800">
								{{ __('Total: {0}% (should be 100%)', [totalAllocation]) }}
							</span>
						</div>
					</div>

					<!-- Available Sales Persons Dropdown -->
					<div v-if="filteredSalesPersons.length > 0 && salesPersonSearch" class="max-h-48 overflow-y-auto border border-purple-200 rounded-lg bg-white">
						<div
							v-for="person in filteredSalesPersons"
							:key="person.name"
							@click="addSalesPerson(person)"
							class="flex items-center justify-between p-2 hover:bg-purple-50 cursor-pointer border-b border-purple-100 last:border-b-0 transition-colors"
						>
							<div class="flex items-center gap-2">
								<svg class="w-4 h-4 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
								</svg>
								<div>
									<div class="text-xs font-medium text-gray-900">
										{{ person.sales_person_name || person.name }}
									</div>
									<div v-if="person.commission_rate" class="text-[10px] text-gray-500">
										{{ __('Commission: {0}%', [person.commission_rate]) }}
									</div>
								</div>
							</div>
						</div>
					</div>

					<!-- Empty State -->
					<div v-else-if="!salesPersonSearch && selectedSalesPersons.length === 0 && !loadingSalesPersons" class="text-center py-3">
						<svg class="w-8 h-8 text-gray-300 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
						</svg>
						<div class="text-xs text-gray-500">{{ __('Search to add sales persons') }}</div>
					</div>

					<!-- Loading State -->
					<div v-if="loadingSalesPersons" class="text-center py-3">
						<div class="text-xs text-gray-500">{{ __('Loading sales persons...') }}</div>
					</div>

					<!-- No Results -->
					<div v-if="salesPersonSearch && filteredSalesPersons.length === 0 && !loadingSalesPersons" class="text-center py-3">
						<div class="text-xs text-gray-500">{{ __('No sales persons found') }}</div>
					</div>
				</div>

				<!-- Additional Discount Section (Compact) -->
				<div v-if="settingsStore.allowAdditionalDiscount" class="bg-gradient-to-r from-orange-50 to-red-50 border border-orange-300 rounded-lg p-2">
					<div class="flex items-center justify-between mb-1.5">
						<div class="flex items-center gap-1.5">
							<div class="w-5 h-5 rounded-full bg-orange-200 flex items-center justify-center">
								<svg class="w-3 h-3 text-orange-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
								</svg>
							</div>
							<span class="text-[11px] font-bold text-orange-900">{{ __('Additional Discount') }}</span>
							<span v-if="localAdditionalDiscount > 0" class="text-[10px] font-bold text-red-600 bg-red-100 px-1.5 py-0.5 rounded">
								-{{ formatCurrency(additionalDiscountType === 'percentage' ? (subtotal * localAdditionalDiscount / 100) : localAdditionalDiscount) }}
							</span>
						</div>
						<button
							v-if="localAdditionalDiscount > 0"
							@click="clearAdditionalDiscount"
							class="text-[10px] text-orange-700 hover:text-orange-900 font-semibold px-1.5 py-0.5 bg-orange-100 hover:bg-orange-200 rounded transition-colors"
						>
							{{ __('Clear') }}
						</button>
					</div>
					<div class="grid grid-cols-[100px_1fr] gap-1.5">
						<!-- Discount Type Selector (Compact) -->
						<select
							v-model="additionalDiscountType"
							@change="handleAdditionalDiscountTypeChange"
							class="w-full px-1.5 py-1.5 text-[11px] font-medium border border-orange-300 rounded focus:outline-none focus:ring-1 focus:ring-orange-500 focus:border-transparent bg-white"
						>
							<option value="percentage">{{ __('% Percent') }}</option>
							<option value="amount">{{ __('{0} Amount', [currencySymbol]) }}</option>
						</select>
						<!-- Discount Value Input (Compact) -->
						<div class="relative">
							<span v-if="additionalDiscountType === 'amount'" class="absolute start-2 top-1/2 -translate-y-1/2 text-gray-600 text-[11px] font-medium">{{ currencySymbol }}</span>
							<input
								type="number"
								v-model.number="localAdditionalDiscount"
								@input="handleAdditionalDiscountChange"
								placeholder="0.00"
								min="0"
								:max="additionalDiscountType === 'percentage' ? 100 : subtotal"
								step="0.01"
								:class="[
									'w-full py-1.5 text-[11px] font-semibold border border-orange-300 rounded focus:outline-none focus:ring-1 focus:ring-orange-500 focus:border-transparent bg-white placeholder-gray-400',
									additionalDiscountType === 'amount' ? 'ps-9 pe-2' : 'px-2 pe-6'
								]"
							/>
							<span v-if="additionalDiscountType === 'percentage'" class="absolute end-2 top-1/2 -translate-y-1/2 text-gray-600 text-[11px] font-medium">%</span>
						</div>
					</div>
				</div>

				<!-- POS M-Pesa Quick Pay -->
				<div
					v-if="!isOffline && (checkingMpesa || mpesaAvailable)"
					class="rounded-lg border border-green-200 bg-green-50 p-3"
				>
					<div class="flex items-center justify-between gap-3">
						<div class="flex items-center gap-2">
							<div class="flex h-8 w-8 items-center justify-center rounded-lg bg-green-600 text-white">
								<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"/>
								</svg>
							</div>
							<div>
								<div class="text-xs font-bold text-green-900">{{ __('Quick Pay - POS M-Pesa') }}</div>
								<div class="text-[11px] text-green-700">
									<span v-if="checkingMpesa">{{ __('Checking M-Pesa setup...') }}</span>
									<span v-else>{{ __('Search M-Pesa C2B register payments and add them to this sale') }}</span>
								</div>
							</div>
						</div>
						<button
							v-if="mpesaAvailable"
							@click="toggleMpesaPanel"
							class="h-9 rounded-lg bg-green-600 px-3 text-xs font-semibold text-white transition-colors hover:bg-green-700"
						>
							{{ showMpesaPanel ? __('Hide') : __('Find Payments') }}
						</button>
					</div>

					<div v-if="mpesaAvailable" class="mt-3 grid gap-2 rounded-lg border border-green-200 bg-white p-3 sm:grid-cols-[1fr_auto_auto] sm:items-end">
						<div>
							<label class="mb-1 block text-[11px] font-semibold text-green-900">
								{{ __('Customer Phone') }}
							</label>
							<input
								v-model="mpesaStkPhone"
								type="tel"
								:placeholder="__('2547XXXXXXXX')"
								class="w-full rounded-lg border border-green-200 px-3 py-2 text-xs focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
							/>
						</div>
						<div class="rounded-lg bg-green-50 px-3 py-2 text-xs">
							<div class="font-semibold text-green-900">{{ __('Request Amount') }}</div>
							<div class="font-bold text-green-700">{{ formatCurrency(mpesaStkAmount) }}</div>
						</div>
						<button
							@click="requestMpesaStkPayment"
							:disabled="sendingMpesaStk || pollingMpesaStk || !mpesaStkAmount"
							:class="[
								'h-9 rounded-lg px-3 text-xs font-semibold transition-colors',
								sendingMpesaStk || pollingMpesaStk || !mpesaStkAmount
									? 'cursor-not-allowed bg-green-200 text-white'
									: 'bg-green-600 text-white hover:bg-green-700'
							]"
						>
							{{ sendingMpesaStk ? __('Requesting...') : pollingMpesaStk ? __('Waiting...') : __('Request Pay') }}
						</button>
					</div>

					<div
						v-if="mpesaStkRequest || mpesaStkMatch"
						class="mt-3 rounded-lg border border-green-200 bg-white p-3"
					>
						<div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
							<div>
								<div class="text-xs font-bold text-green-900">
									{{ mpesaStkMatch ? __('M-Pesa payment received') : __('STK request sent') }}
								</div>
								<div class="text-[11px] text-green-700">
									{{ mpesaStkStatusMessage }}
								</div>
								<div v-if="mpesaStkRequest?.invoice" class="mt-1 text-[11px] text-gray-500">
									{{ __('Invoice: {0}', [mpesaStkRequest.invoice]) }}
								</div>
							</div>
							<button
								v-if="mpesaStkMatch"
								@click="addDetectedMpesaPayment"
								:disabled="isMpesaAlreadyAdded(mpesaStkMatch.name)"
								class="h-9 rounded-lg bg-green-600 px-3 text-xs font-semibold text-white transition-colors hover:bg-green-700 disabled:cursor-not-allowed disabled:bg-green-200"
							>
								{{ isMpesaAlreadyAdded(mpesaStkMatch.name) ? __('Added') : __('Add Payment') }}
							</button>
						</div>
					</div>

					<div v-if="showMpesaPanel" class="mt-3 rounded-lg border border-green-200 bg-white p-3">
						<div class="flex flex-col gap-2 sm:flex-row sm:items-center">
							<div class="relative flex-1">
								<input
									v-model="mpesaSearch"
									type="text"
									:placeholder="__('Search C2B name, phone, transaction ID')"
									class="w-full rounded-lg border border-green-200 px-3 py-2 ps-8 text-xs focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
									@input="handleMpesaSearchInput"
								/>
								<svg class="absolute start-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
								</svg>
							</div>
							<div class="rounded-lg bg-green-100 px-3 py-2 text-xs font-semibold text-green-800">
								{{ __('Latest pending payments') }}
							</div>
						</div>

						<div class="mt-3 max-h-56 overflow-y-auto rounded-lg border border-gray-200">
							<div v-if="loadingMpesaPayments" class="flex items-center justify-center gap-2 p-4 text-xs text-gray-500">
								<div class="h-4 w-4 animate-spin rounded-full border-b-2 border-green-600"></div>
								<span>{{ __('Loading M-Pesa payments...') }}</span>
							</div>
							<div v-else-if="mpesaPendingCount === 0" class="p-4 text-center text-xs text-gray-500">
								{{ __('No pending M-Pesa payments found') }}
							</div>
							<div v-else-if="mpesaPayments.length === 0" class="p-4 text-center text-xs text-gray-500">
								{{ __('No matching M-Pesa payments') }}
							</div>
							<template v-else>
								<button
									v-for="payment in mpesaPayments"
									:key="payment.name"
									@click="toggleMpesaPayment(payment)"
									:class="[
										'flex w-full items-center gap-3 border-b border-gray-100 p-3 text-start last:border-b-0 transition-colors',
										isMpesaAlreadyAdded(payment.name)
											? 'bg-green-50'
											: 'hover:bg-green-50'
									]"
								>
									<input
										type="checkbox"
										:checked="isMpesaAlreadyAdded(payment.name)"
										class="h-4 w-4 accent-green-600"
										@click.stop="toggleMpesaPayment(payment)"
									/>
									<div class="min-w-0 flex-1">
										<div class="flex items-center justify-between gap-2">
											<div class="truncate text-xs font-semibold text-gray-900">
												{{ payment.full_name || __('Unknown') }}
											</div>
											<div class="text-xs font-bold text-green-700">
												{{ formatCurrency(payment.transamount) }}
											</div>
										</div>
										<div class="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-gray-500">
											<span>{{ payment.msisdn || __('No phone') }}</span>
											<span>{{ payment.transid || payment.name }}</span>
											<span v-if="payment.billrefnumber">{{ payment.billrefnumber }}</span>
											<span v-if="payment.match_score" class="font-semibold text-green-700">
												{{ payment.match_level }} - {{ payment.match_reasons?.join(', ') }}
											</span>
										</div>
									</div>
								</button>
							</template>
						</div>

						<div class="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
							<div class="text-xs text-gray-600">
								{{ __('Applied to breakdown: {0} payment(s), {1}', [appliedMpesaPaymentCount, formatCurrency(appliedMpesaTotal)]) }}
							</div>
							<div class="text-xs font-medium text-green-700">
								{{ __('Tick to add, untick to remove') }}
							</div>
						</div>
					</div>
				</div>

				<!-- SMS Enabler Quick Pay -->
				<div
					v-if="!isOffline && (checkingSmsEnabler || smsEnablerAvailable)"
					class="rounded-lg border border-emerald-200 bg-emerald-50 p-3"
				>
					<div class="flex items-center justify-between gap-3">
						<div class="flex items-center gap-2">
							<div class="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600 text-white">
								<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 4v-4z"/>
								</svg>
							</div>
							<div>
								<div class="text-xs font-bold text-emerald-900">{{ __('Quick Pay - SMS Enabler') }}</div>
								<div class="text-[11px] text-emerald-700">
									<span v-if="checkingSmsEnabler">{{ __('Checking SMS Enabler setup...') }}</span>
									<span v-else>{{ __('Use bank paybill SMS payments from SMS Enabler') }}</span>
								</div>
							</div>
						</div>
						<button
							v-if="smsEnablerAvailable"
							@click="toggleSmsEnablerPanel"
							class="h-9 rounded-lg bg-emerald-600 px-3 text-xs font-semibold text-white transition-colors hover:bg-emerald-700"
						>
							{{ showSmsEnablerPanel ? __('Hide') : __('Find SMS Payments') }}
						</button>
					</div>

					<div v-if="showSmsEnablerPanel" class="mt-3 rounded-lg border border-emerald-200 bg-white p-3">
						<div class="mb-2 rounded-lg bg-emerald-50 px-3 py-2 text-[11px] text-emerald-800">
							{{ __('Mode: {0}', [smsReconciliationMode]) }}
						</div>
						<div class="flex flex-col gap-2 sm:flex-row sm:items-center">
							<div class="relative flex-1">
								<input
									v-model="smsEnablerSearch"
									type="text"
									:placeholder="__('Search SMS payer, phone, transaction ID, account')"
									class="w-full rounded-lg border border-emerald-200 px-3 py-2 ps-8 text-xs focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
									@input="handleSmsEnablerSearchInput"
								/>
								<svg class="absolute start-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
								</svg>
							</div>
							<div class="rounded-lg bg-emerald-100 px-3 py-2 text-xs font-semibold text-emerald-800">
								{{ __('Latest pending SMS payments') }}
							</div>
						</div>

						<div class="mt-3 max-h-56 overflow-y-auto rounded-lg border border-gray-200">
							<div v-if="loadingSmsEnablerPayments" class="flex items-center justify-center gap-2 p-4 text-xs text-gray-500">
								<div class="h-4 w-4 animate-spin rounded-full border-b-2 border-emerald-600"></div>
								<span>{{ __('Loading SMS payments...') }}</span>
							</div>
							<div v-else-if="smsEnablerPendingCount === 0" class="p-4 text-center text-xs text-gray-500">
								{{ __('No pending SMS payments found') }}
							</div>
							<div v-else-if="smsEnablerPayments.length === 0" class="p-4 text-center text-xs text-gray-500">
								{{ __('No matching SMS payments') }}
							</div>
							<template v-else>
								<button
									v-for="payment in smsEnablerPayments"
									:key="payment.name"
									@click="toggleSmsEnablerPayment(payment)"
									:class="[
										'flex w-full items-center gap-3 border-b border-gray-100 p-3 text-start last:border-b-0 transition-colors',
										isSmsEnablerAlreadyAdded(payment.name)
											? 'bg-emerald-50'
											: 'hover:bg-emerald-50'
									]"
								>
									<input
										type="checkbox"
										:checked="isSmsEnablerAlreadyAdded(payment.name)"
										class="h-4 w-4 accent-emerald-600"
										@click.stop="toggleSmsEnablerPayment(payment)"
									/>
									<div class="min-w-0 flex-1">
										<div class="flex items-center justify-between gap-2">
											<div class="truncate text-xs font-semibold text-gray-900">
												{{ payment.payer_name || payment.source || __('Unknown') }}
											</div>
											<div class="text-xs font-bold text-emerald-700">
												{{ formatCurrency(payment.amount) }}
											</div>
										</div>
										<div class="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-gray-500">
											<span>{{ payment.source || __('SMS') }}</span>
											<span>{{ payment.payer_phone || payment.sender || __('No phone') }}</span>
											<span>{{ payment.transaction_id || payment.name }}</span>
											<span v-if="payment.account_reference">{{ payment.account_reference }}</span>
											<span v-if="payment.match_score" class="font-semibold text-emerald-700">
												{{ payment.match_level }} - {{ payment.match_reasons?.join(', ') }}
											</span>
										</div>
									</div>
								</button>
							</template>
						</div>

						<div class="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
							<div class="text-xs text-gray-600">
								{{ __('Applied to breakdown: {0} payment(s), {1}', [appliedSmsEnablerPaymentCount, formatCurrency(appliedSmsEnablerTotal)]) }}
							</div>
							<div class="text-xs font-medium text-emerald-700">
								{{ __('Tick to add, untick to remove') }}
							</div>
						</div>
					</div>
				</div>

				<!-- Payment Methods Grid -->
				<div class="text-start mb-3">
					<h3 class="text-sm font-semibold text-gray-700 mb-1">{{ __('Payment Methods') }}</h3>
					<div class="text-xs text-gray-500">
						{{ __('Select payment method to add') }}
					</div>
					<!-- Loading State -->
					<div v-if="loadingPaymentMethods" class="flex items-center justify-center py-8">
						<div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
						<span class="ms-3 text-sm text-gray-500">{{ __('Loading payment methods...') }}</span>
					</div>
					<!-- Payment Methods -->
					<div v-else-if="paymentMethods.length > 0" class="grid grid-cols-2 md:grid-cols-3 gap-3 mt-3">
						<button
							v-for="method in paymentMethods"
							:key="method.mode_of_payment"
							@click="quickAddPayment(method)"
							:class="[
								'group relative p-4 rounded-xl border-2 transition-all text-start',
								'hover:shadow-lg transform hover:-translate-y-0.5',
								'cursor-pointer',
								'border-gray-200 hover:border-blue-400 bg-white hover:bg-blue-50'
							]"
						>
							<div class="flex items-start justify-between">
								<div class="flex-1">
									<div class="flex items-center mb-1">
										<span class="text-2xl me-2">{{ getPaymentIcon(method.type) }}</span>
										<div>
											<div class="font-semibold text-sm text-gray-900">
												{{ method.mode_of_payment }}
											</div>
											<div class="text-xs text-gray-500">{{ method.type || __('Cash') }}</div>
										</div>
									</div>
								</div>
								<div class="opacity-0 group-hover:opacity-100 transition-opacity">
									<svg class="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
									</svg>
								</div>
							</div>
							<div v-if="getMethodTotal(method.mode_of_payment) > 0"
								class="mt-2 pt-2 border-t border-gray-200">
								<div class="text-xs text-gray-500">{{ __('Added') }}</div>
								<div class="font-bold text-blue-600">
									{{ formatCurrency(getMethodTotal(method.mode_of_payment)) }}
								</div>
							</div>
						</button>
					</div>
					<!-- Empty State -->
					<div v-else class="text-center py-8 text-gray-500">
						<svg class="mx-auto h-10 w-10 text-gray-400 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/>
						</svg>
						<p class="text-sm">{{ __('No payment methods available') }}</p>
					</div>
				</div>

				<!-- Quick Amount Buttons -->
				<div v-if="remainingAmount > 0 && lastSelectedMethod" class="bg-gray-50 rounded-lg p-4 border border-gray-200">
					<div class="text-start text-xs font-medium text-gray-600 mb-2">
						{{ __('Quick amounts for {0}', [lastSelectedMethod.mode_of_payment]) }}
					</div>
					<div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
						<button
							v-for="amount in quickAmounts"
							:key="amount"
							@click="addCustomPayment(lastSelectedMethod, amount)"
							class="px-4 py-3 text-sm font-semibold rounded-lg bg-white border-2 border-gray-200 hover:border-blue-400 hover:bg-blue-50 text-gray-700 hover:text-blue-600 transition-all"
						>
							{{ formatCurrency(amount) }}
						</button>
					</div>
					<div class="mt-4">
						<div class="text-start text-xs font-medium text-gray-600 mb-1">{{ __('Custom amount') }}</div>
						<div class="flex gap-2">
							<Input
								v-model="customAmount"
								type="number"
								step="5"
								min="0"
								placeholder="0.00"
								class="flex-1"
								@keyup.enter="addCustomPayment(lastSelectedMethod, customAmount)"
							/>
							<Button
								variant="solid"
								theme="blue"
								@click="addCustomPayment(lastSelectedMethod, customAmount)"
								:disabled="!customAmount || customAmount <= 0"
							>
								{{ __('Add') }}
							</Button>
						</div>
					</div>
				</div>

				<!-- Active Payment Entries -->
				<div v-if="paymentEntries.length > 0">
					<h3 class="text-start text-sm font-semibold text-gray-700 mb-3">{{ __('Payment Breakdown') }}</h3>
					<div class="flex flex-col gap-2 max-h-64 overflow-y-auto">
						<div
							v-for="(entry, index) in paymentEntries"
							:key="index"
							class="group flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between p-3 bg-white rounded-lg border-2 border-gray-200 hover:border-red-300 transition-all"
						>
							<div class="flex items-center gap-3 min-w-0 flex-1">
								<span class="text-xl">{{ getPaymentIcon(entry.type) }}</span>
								<div class="min-w-0 flex-1">
									<select
										v-if="!isPaymentEntryLocked(entry)"
										v-model="entry.mode_of_payment"
										@change="updatePaymentMethod(index, $event.target.value)"
										class="w-full sm:w-56 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-900 focus:border-transparent focus:ring-2 focus:ring-blue-500"
									>
										<option
											v-for="method in paymentMethods"
											:key="method.mode_of_payment"
											:value="method.mode_of_payment"
										>
											{{ method.mode_of_payment }}
										</option>
									</select>
									<div v-else class="font-medium text-sm text-gray-900">{{ entry.mode_of_payment }}</div>
									<div class="text-xs text-gray-500">
										{{ entry.is_mpesa
											? __('POS M-Pesa {0}', [entry.mpesa_transaction_id])
											: entry.is_sms_enabler
											? __('SMS Enabler {0}', [entry.sms_transaction_id])
											: entry.type }}
									</div>
									<input
										v-model="entry.reference_no"
										type="text"
										maxlength="140"
										:placeholder="__('Reference code (optional)')"
										:disabled="!canEditPaymentDetails(entry)"
										class="mt-2 w-full sm:w-56 px-3 py-1.5 text-xs text-gray-700 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-500"
										@blur="normalizePaymentReference(index)"
									/>
								</div>
							</div>
							<div class="flex items-center justify-end gap-4">
								<input
									v-model.number="entry.amount"
									type="number"
									inputmode="decimal"
									step="0.01"
									min="0"
									:disabled="!canEditPaymentDetails(entry)"
									class="w-32 px-3 py-1 text-end font-bold text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-500"
									@focus="$event.target.select()"
									@blur="normalizePaymentAmount(index)"
								/>
								<button
									@click="removePaymentEntry(index)"
									class="p-1 text-red-500 hover:text-red-700 hover:bg-red-50 rounded-lg transition-all sm:opacity-0 sm:group-hover:opacity-100"
								>
									<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
									</svg>
								</button>
							</div>
						</div>
					</div>
				</div>
			</div>
		</template>

		<template #actions>
			<!-- Mobile Layout: Stacked buttons -->
			<div class="flex flex-col w-full gap-2 sm:hidden">
				<!-- Complete/Partial Payment Button -->
				<button
					@click="completePayment"
					:disabled="!canComplete"
					:class="[
						'w-full inline-flex items-center justify-center gap-2 transition-colors focus:outline-none',
						'h-12 text-base font-semibold px-4 rounded-lg touch-manipulation',
						!canComplete
							? 'bg-blue-300 text-white cursor-not-allowed'
							: 'bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800 focus-visible:ring-2 focus-visible:ring-blue-400'
					]"
				>
					<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
						<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
					</svg>
					<span>{{ paymentButtonText }}</span>
				</button>

				<!-- Pay on Account Button (if credit sales enabled) -->
				<button
					v-if="allowCreditSale"
					@click="addCreditAccountPayment"
					:disabled="paymentEntries.length > 0"
					:class="[
						'w-full inline-flex items-center justify-center gap-2 transition-colors focus:outline-none',
						'h-12 text-base font-semibold px-4 rounded-lg touch-manipulation',
						paymentEntries.length > 0
							? 'bg-orange-300 text-white cursor-not-allowed'
							: 'bg-orange-500 text-white hover:bg-orange-600 active:bg-orange-700 focus-visible:ring-2 focus-visible:ring-orange-400'
					]"
				>
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
					</svg>
					<span>{{ __('Pay on Account') }}</span>
				</button>

				<!-- Apply Credit Button (if available) - full width on mobile -->
				<button
					v-if="allowCreditSale && totalAvailableCredit > 0 && remainingAmount > 0"
					@click="applyCustomerCredit"
					class="w-full inline-flex items-center justify-center gap-2 h-11 px-4 text-sm font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 active:bg-emerald-200 rounded-lg transition-colors touch-manipulation"
				>
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
					</svg>
					<span>{{ __('Apply Credit') }}</span>
				</button>

				<!-- Secondary row: Clear and Cancel - equal width side by side -->
				<div class="flex items-center gap-2 mt-1">
					<button
						@click="clearAll"
						:disabled="paymentEntries.length === 0"
						:class="[
							'flex-1 inline-flex items-center justify-center gap-1.5 h-11 px-3 text-sm font-medium rounded-lg transition-colors touch-manipulation',
							paymentEntries.length === 0
								? 'text-gray-400 bg-gray-50 cursor-not-allowed'
								: 'text-red-600 bg-red-50 hover:bg-red-100 active:bg-red-200'
						]"
					>
						<svg class="w-4 h-4 rtl:scale-x-[-1]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
						</svg>
						<span>{{ __('Clear') }}</span>
					</button>

					<button
						@click="show = false"
						class="flex-1 inline-flex items-center justify-center gap-1.5 h-11 px-3 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 active:bg-gray-300 rounded-lg transition-colors touch-manipulation"
					>
						<span>{{ __('Cancel') }}</span>
					</button>
				</div>
			</div>

			<!-- Desktop Layout: Single row with proper alignment -->
			<div class="hidden sm:flex items-center justify-between w-full gap-3">
				<!-- Start: Secondary actions -->
				<div class="flex items-center gap-2">
					<!-- Clear Button -->
					<button
						v-if="paymentEntries.length > 0"
						@click="clearAll"
						class="inline-flex items-center justify-center gap-1.5 h-9 px-3 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 active:bg-red-200 rounded-lg transition-colors"
					>
						<svg class="w-4 h-4 rtl:scale-x-[-1]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
						</svg>
						<span>{{ __('Clear All') }}</span>
					</button>

					<!-- Apply Credit Button (if available) -->
					<button
						v-if="allowCreditSale && totalAvailableCredit > 0 && remainingAmount > 0"
						@click="applyCustomerCredit"
						class="inline-flex items-center justify-center gap-1.5 h-9 px-3 text-sm font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 active:bg-emerald-200 rounded-lg transition-colors"
					>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
						</svg>
						<span>{{ __('Apply Credit') }}</span>
					</button>
				</div>

				<!-- End: Primary actions -->
				<div class="flex items-center gap-2">
					<!-- Cancel Button -->
					<button
						@click="show = false"
						class="inline-flex items-center justify-center h-9 px-4 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 active:bg-gray-300 rounded-lg transition-colors"
					>
						{{ __('Cancel') }}
					</button>

					<!-- Pay on Account Button (if credit sales enabled) -->
					<button
						v-if="allowCreditSale"
						@click="addCreditAccountPayment"
						:disabled="paymentEntries.length > 0"
						:class="[
							'inline-flex items-center justify-center gap-2 transition-colors focus:outline-none',
							'h-9 text-sm font-semibold px-4 rounded-lg',
							paymentEntries.length > 0
								? 'bg-orange-300 text-white cursor-not-allowed'
								: 'bg-orange-500 text-white hover:bg-orange-600 active:bg-orange-700 focus-visible:ring-2 focus-visible:ring-orange-400'
						]"
					>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
						</svg>
						<span>{{ __('Pay on Account') }}</span>
					</button>

					<!-- Complete/Partial Payment Button -->
					<button
						@click="completePayment"
						:disabled="!canComplete"
						:class="[
							'inline-flex items-center justify-center gap-2 transition-colors focus:outline-none',
							'h-9 text-sm font-semibold px-5 rounded-lg',
							!canComplete
								? 'bg-blue-300 text-white cursor-not-allowed'
								: 'bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800 focus-visible:ring-2 focus-visible:ring-blue-400'
						]"
					>
						<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
							<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
						</svg>
						<span>{{ paymentButtonText }}</span>
					</button>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { usePOSSettingsStore } from "@/stores/posSettings"
import { formatCurrency as formatCurrencyUtil, getCurrencySymbol } from "@/utils/currency"
import { call } from "@/utils/apiWrapper"
import { getPaymentIcon } from "@/utils/payment"
import { offlineWorker } from "@/utils/offline/workerClient"
import { Button, Dialog, Input, createResource } from "frappe-ui"
import { computed, onUnmounted, ref, watch } from "vue"
import { useToast } from "@/composables/useToast"

const settingsStore = usePOSSettingsStore()
const { showSuccess, showWarning, showError } = useToast()

const props = defineProps({
	modelValue: Boolean,
	grandTotal: {
		type: Number,
		default: 0,
	},
	subtotal: {
		type: Number,
		default: 0,
	},
	posProfile: String,
	currency: {
		type: String,
		default: "USD",
	},
	isOffline: {
		type: Boolean,
		default: false,
	},
	allowPartialPayment: {
		type: Boolean,
		default: false,
	},
	allowCreditSale: {
		type: Boolean,
		default: false,
	},
	customer: {
		type: [String, Object],
		default: null,
	},
	company: {
		type: String,
		default: "",
	},
	additionalDiscount: {
		type: Number,
		default: 0,
	},
	requestMpesaStk: {
		type: Function,
		default: null,
	},
})

const emit = defineEmits(["update:modelValue", "payment-completed", "update-additional-discount"])

const show = computed({
	get: () => props.modelValue,
	set: (val) => emit("update:modelValue", val),
})

const paymentMethods = ref([])
const loadingPaymentMethods = ref(false)
const lastSelectedMethod = ref(null)
const customAmount = ref("")
const paymentEntries = ref([])
const customerCredit = ref([])
const customerBalance = ref({ total_outstanding: 0, total_credit: 0, net_balance: 0 })
const loadingCredit = ref(false)
const mpesaAvailable = ref(false)
const mpesaModeOfPayment = ref("")
const checkingMpesa = ref(false)
const showMpesaPanel = ref(false)
const loadingMpesaPayments = ref(false)
const mpesaPendingCount = ref(0)
const mpesaPayments = ref([])
const mpesaSearch = ref("")
const selectedMpesaPayments = ref([])
const mpesaStkPhone = ref("")
const sendingMpesaStk = ref(false)
const pollingMpesaStk = ref(false)
const mpesaStkRequest = ref(null)
const mpesaStkMatch = ref(null)
const mpesaStkStatusMessage = ref("")
const mpesaStkPollAttempts = ref(0)
let mpesaSearchTimeout = null
let mpesaStkPollTimer = null
const smsEnablerAvailable = ref(false)
const smsEnablerModeOfPayment = ref("")
const checkingSmsEnabler = ref(false)
const showSmsEnablerPanel = ref(false)
const loadingSmsEnablerPayments = ref(false)
const smsEnablerPendingCount = ref(0)
const smsEnablerPayments = ref([])
const smsEnablerSearch = ref("")
const selectedSmsEnablerPayments = ref([])
const smsEnablerAutoApplied = ref(false)
let smsEnablerSearchTimeout = null

// Additional discount state
const localAdditionalDiscount = ref(0)
// Initialize discount type from settings (default to percentage if enabled, otherwise amount)
const additionalDiscountType = ref(
	settingsStore.usePercentageDiscount ? 'percentage' : 'amount'
)

const paymentMethodsResource = createResource({
	url: "pos_next.api.pos_profile.get_payment_methods",
	makeParams() {
		return {
			pos_profile: props.posProfile,
		}
	},
	auto: false,
	onSuccess(data) {
		paymentMethods.value = data?.message || data || []
		// Set first method as last selected for quick amounts
		if (paymentMethods.value.length > 0) {
			const defaultMethod = paymentMethods.value.find((m) => m.default)
			lastSelectedMethod.value = defaultMethod || paymentMethods.value[0]
		}
	},
})

const customerCreditResource = createResource({
	url: "pos_next.api.credit_sales.get_available_credit",
	makeParams() {
		const customerName = props.customer?.name || props.customer
		console.log('[PaymentDialog] Fetching credit for customer:', customerName)
		return {
			customer: customerName,
			company: props.company,
			pos_profile: props.posProfile,
		}
	},
	auto: false,
	onSuccess(data) {
		console.log('[PaymentDialog] Customer credit loaded:', data)
		customerCredit.value = data || []
		loadingCredit.value = false
		console.log('[PaymentDialog] Total available credit:', totalAvailableCredit.value)
	},
	onError(error) {
		console.error("[PaymentDialog] Error loading customer credit:", error)
		customerCredit.value = []
		loadingCredit.value = false
	},
})

const customerBalanceResource = createResource({
	url: "pos_next.api.credit_sales.get_customer_balance",
	makeParams() {
		const customerName = props.customer?.name || props.customer
		console.log('[PaymentDialog] Fetching balance for customer:', customerName)
		return {
			customer: customerName,
			company: props.company,
		}
	},
	auto: false,
	onSuccess(data) {
		console.log('[PaymentDialog] Customer balance loaded:', data)
		customerBalance.value = data || { total_outstanding: 0, total_credit: 0, net_balance: 0 }
		console.log('[PaymentDialog] Net balance:', customerBalance.value.net_balance)
	},
	onError(error) {
		console.error("[PaymentDialog] Error loading customer balance:", error)
		customerBalance.value = { total_outstanding: 0, total_credit: 0, net_balance: 0 }
	},
})

// Sales Persons state
const salesPersons = ref([])
const selectedSalesPersons = ref([])
const salesPersonSearch = ref('')
const loadingSalesPersons = ref(false)

const salesPersonsResource = createResource({
	url: "pos_next.api.pos_profile.get_sales_persons",
	makeParams() {
		return {
			pos_profile: props.posProfile,
		}
	},
	auto: false,
	onSuccess(data) {
		console.log('[PaymentDialog] Sales persons loaded:', data)
		salesPersons.value = data?.message || data || []
		loadingSalesPersons.value = false
	},
	onError(error) {
		console.error("[PaymentDialog] Error loading sales persons:", error)
		salesPersons.value = []
		loadingSalesPersons.value = false
	},
})

// Computed: Filter sales persons based on search and exclude already selected
const filteredSalesPersons = computed(() => {
	if (!salesPersonSearch.value) {
		return []
	}

	const searchLower = salesPersonSearch.value.toLowerCase()
	const selectedIds = selectedSalesPersons.value.map(p => p.sales_person)

	return salesPersons.value
		.filter(person => {
			// Exclude already selected
			if (selectedIds.includes(person.name)) {
				return false
			}
			// Filter by search term
			const name = (person.sales_person_name || person.name || '').toLowerCase()
			return name.includes(searchLower)
		})
		.slice(0, 10) // Limit to 10 results for performance
})

// Computed for total allocation percentage
const totalAllocation = computed(() => {
	return selectedSalesPersons.value.reduce((sum, person) => {
		return sum + (person.allocated_percentage || 0)
	}, 0)
})

// Helper functions for sales persons
function addSalesPerson(person) {
	// For Single mode, replace the existing selection
	if (settingsStore.isSingleSalesPerson) {
		selectedSalesPersons.value = [{
			sales_person: person.name,
			sales_person_name: person.sales_person_name || person.name,
			allocated_percentage: 100, // Always 100% for single mode
			commission_rate: person.commission_rate,
		}]
	} else {
		// For Multiple mode, add to the list
		// Calculate default allocation
		const defaultAllocation = selectedSalesPersons.value.length === 0 ? 100 : 0

		selectedSalesPersons.value.push({
			sales_person: person.name,
			sales_person_name: person.sales_person_name || person.name,
			allocated_percentage: defaultAllocation,
			commission_rate: person.commission_rate,
		})
	}

	// Clear search after adding
	salesPersonSearch.value = ''
}

function removeSalesPerson(personName) {
	const index = selectedSalesPersons.value.findIndex(p => p.sales_person === personName)
	if (index > -1) {
		selectedSalesPersons.value.splice(index, 1)
	}
}

function updateSalesPersonAllocation(personName, value) {
	const person = selectedSalesPersons.value.find(p => p.sales_person === personName)
	if (person) {
		person.allocated_percentage = Number.parseFloat(value) || 0
	}
}

function clearSalesPersons() {
	selectedSalesPersons.value = []
	salesPersonSearch.value = ''
}

// Load payment methods - from cache if offline, from server if online
async function loadPaymentMethods() {
	// Guard: Don't load if posProfile is not set or already loading
	if (!props.posProfile) {
		console.warn(
			"PaymentDialog: Cannot load payment methods - posProfile is not set",
		)
		return
	}

	// Skip if already loading or already loaded for this profile
	if (loadingPaymentMethods.value) {
		return
	}

	loadingPaymentMethods.value = true

	try {
		if (props.isOffline) {
			// Load from cache when offline using worker
			const cached = await offlineWorker.getCachedPaymentMethods(props.posProfile)
			if (cached && cached.length > 0) {
				paymentMethods.value = cached
				if (paymentMethods.value.length > 0) {
					const defaultMethod = paymentMethods.value.find((m) => m.default)
					lastSelectedMethod.value = defaultMethod || paymentMethods.value[0]
				}
			}
		} else {
			// Load from server when online
			await paymentMethodsResource.fetch()
		}
	} catch (error) {
		console.error("Error loading payment methods:", error)
	} finally {
		loadingPaymentMethods.value = false
	}
}

async function checkMpesaAvailability() {
	mpesaAvailable.value = false
	mpesaModeOfPayment.value = ""
	checkingMpesa.value = false

	if (props.isOffline || (!props.company && !props.posProfile)) {
		return
	}

	checkingMpesa.value = true

	try {
		const result = await call("pos_next.api.mpesa.check_mpesa_available", {
			company: props.company,
			pos_profile: props.posProfile,
		})

		mpesaAvailable.value = Boolean(result?.available)
		mpesaModeOfPayment.value = result?.mode_of_payment || ""
		if (mpesaAvailable.value) {
			prefillMpesaStkPhone()
		}
	} catch (error) {
		console.warn("[PaymentDialog] M-Pesa availability check failed:", error)
		mpesaAvailable.value = false
	} finally {
		checkingMpesa.value = false
	}
}

async function prefillMpesaStkPhone() {
	if (mpesaStkPhone.value || !props.customer) {
		return
	}

	try {
		const result = await call("pos_next.api.mpesa.get_customer_phone", {
			customer: props.customer?.name || props.customer,
		})
		if (result) {
			mpesaStkPhone.value = result
		}
	} catch (error) {
		console.warn("[PaymentDialog] Failed to load customer phone for STK:", error)
	}
}

async function loadMpesaPayments(search = mpesaSearch.value) {
	if (!mpesaAvailable.value || props.isOffline) {
		return
	}

	loadingMpesaPayments.value = true

	try {
		const result = await call("pos_next.api.mpesa.get_mpesa_payments", {
			company: props.company,
			pos_profile: props.posProfile,
			search,
		})

		mpesaPendingCount.value = result?.count || 0
		mpesaPayments.value = result?.payments || []
	} catch (error) {
		console.error("[PaymentDialog] Failed to load M-Pesa payments:", error)
		showError(error.message || __("Failed to load M-Pesa payments"))
	} finally {
		loadingMpesaPayments.value = false
	}
}

function toggleMpesaPanel() {
	showMpesaPanel.value = !showMpesaPanel.value

	if (showMpesaPanel.value) {
		loadMpesaPayments("")
	}
}

function handleMpesaSearchInput() {
	if (mpesaSearchTimeout) {
		clearTimeout(mpesaSearchTimeout)
	}

	const search = mpesaSearch.value.trim()

	mpesaSearchTimeout = setTimeout(() => {
		loadMpesaPayments(search)
	}, 300)
}

function isMpesaSelected(paymentName) {
	return selectedMpesaPayments.value.some((payment) => payment.name === paymentName)
}

function isMpesaAlreadyAdded(paymentName) {
	return addedMpesaNames.value.includes(paymentName)
}

function addMpesaPayment(payment) {
	if (!payment || isMpesaAlreadyAdded(payment.name)) {
		return
	}

	if (!mpesaModeOfPayment.value) {
		showError(__("No Phone mode of payment is configured for M-Pesa"))
		return
	}

	const amount = Number.parseFloat(payment.transamount || 0)
	if (!amount || amount <= 0) {
		return
	}

	paymentEntries.value.push({
		mode_of_payment: mpesaModeOfPayment.value,
		amount,
		type: "Phone",
		is_mpesa: true,
		mpesa_payment_name: payment.name,
		mpesa_transaction_id: payment.transid || payment.name,
		reference_no: payment.transid || payment.name,
	})
}

function removeMpesaPayment(paymentName) {
	paymentEntries.value = paymentEntries.value.filter(
		(entry) => !(entry.is_mpesa && entry.mpesa_payment_name === paymentName),
	)
}

function toggleMpesaPayment(payment) {
	if (isMpesaAlreadyAdded(payment.name)) {
		removeMpesaPayment(payment.name)
		return
	}

	addMpesaPayment(payment)
}

function addSelectedMpesaPayments() {
	selectedMpesaPayments.value.forEach((payment) => addMpesaPayment(payment))
	selectedMpesaPayments.value = []
}

function stopMpesaStkPolling() {
	if (mpesaStkPollTimer) {
		clearTimeout(mpesaStkPollTimer)
		mpesaStkPollTimer = null
	}
	pollingMpesaStk.value = false
}

async function requestMpesaStkPayment() {
	if (!props.requestMpesaStk) {
		showError(__("STK request handler is not configured"))
		return
	}

	if (!mpesaStkPhone.value.trim()) {
		showWarning(__("Enter the customer's phone number"))
		return
	}

	if (!mpesaStkAmount.value || mpesaStkAmount.value <= 0) {
		showWarning(__("There is no amount to request"))
		return
	}

	sendingMpesaStk.value = true
	stopMpesaStkPolling()
	mpesaStkMatch.value = null
	mpesaStkStatusMessage.value = __("Sending payment request to the customer...")

	try {
		const result = await props.requestMpesaStk({
			phone_number: mpesaStkPhone.value.trim(),
			amount: mpesaStkAmount.value,
		})

		mpesaStkRequest.value = result || {}
		mpesaStkPollAttempts.value = 0
		showMpesaPanel.value = true
		mpesaStkStatusMessage.value = __("Waiting for the customer's M-Pesa confirmation...")
		showSuccess(__("STK payment request sent"))
		await pollMpesaStkPayment()
	} catch (error) {
		console.error("[PaymentDialog] STK request failed:", error)
		mpesaStkStatusMessage.value = error.message || __("Failed to send STK request")
		showError(mpesaStkStatusMessage.value)
	} finally {
		sendingMpesaStk.value = false
	}
}

async function pollMpesaStkPayment() {
	if (!mpesaStkRequest.value?.invoice) {
		return
	}

	pollingMpesaStk.value = true
	mpesaStkPollAttempts.value += 1

	try {
		const result = await call("pos_next.api.mpesa.get_stk_payment_match", {
			invoice: mpesaStkRequest.value.invoice,
			payment_request: mpesaStkRequest.value.payment_request,
			phone_number: mpesaStkRequest.value.phone_number || mpesaStkPhone.value,
			amount: mpesaStkRequest.value.amount || mpesaStkAmount.value,
			company: props.company,
			pos_profile: props.posProfile,
		})

		if (result?.matched && result.payment) {
			stopMpesaStkPolling()
			mpesaStkMatch.value = result.payment
			mpesaPayments.value = [result.payment]
			selectedMpesaPayments.value = [result.payment]
			mpesaPendingCount.value = Math.max(mpesaPendingCount.value, 1)
			mpesaStkStatusMessage.value = __("Review the detected payment, then add it to this sale.")
			showSuccess(__("M-Pesa payment received"))
			return
		}

		if (mpesaStkPollAttempts.value >= 24) {
			stopMpesaStkPolling()
			mpesaStkStatusMessage.value = __("No matching payment received yet. Use Find Payments to search manually.")
			return
		}

		mpesaStkStatusMessage.value = __("Waiting for payment confirmation... checked {0} time(s).", [mpesaStkPollAttempts.value])
		mpesaStkPollTimer = setTimeout(pollMpesaStkPayment, 5000)
	} catch (error) {
		console.error("[PaymentDialog] Failed to poll STK payment:", error)
		stopMpesaStkPolling()
		mpesaStkStatusMessage.value = error.message || __("Could not check for the STK payment")
		showWarning(mpesaStkStatusMessage.value)
	}
}

function addDetectedMpesaPayment() {
	if (!mpesaStkMatch.value) {
		return
	}

	addMpesaPayment(mpesaStkMatch.value)
	showSuccess(__("M-Pesa payment added"))
}

async function checkSmsEnablerAvailability() {
	smsEnablerAvailable.value = false
	smsEnablerModeOfPayment.value = ""
	checkingSmsEnabler.value = false

	if (props.isOffline || (!props.company && !props.posProfile)) {
		return
	}

	checkingSmsEnabler.value = true

	try {
		const result = await call("pos_next.api.smsenabler_mpesa.check_sms_enabler_available", {
			company: props.company,
			pos_profile: props.posProfile,
		})

		smsEnablerAvailable.value = Boolean(result?.available)
		smsEnablerModeOfPayment.value = result?.mode_of_payment || ""

		if (smsEnablerAvailable.value && (isSuggestedSmsReconciliation.value || isAutoSmsReconciliation.value)) {
			showSmsEnablerPanel.value = true
			await loadSmsEnablerPayments("", { suggest: true })
		}
	} catch (error) {
		console.warn("[PaymentDialog] SMS Enabler availability check failed:", error)
		smsEnablerAvailable.value = false
	} finally {
		checkingSmsEnabler.value = false
	}
}

async function loadSmsEnablerPayments(search = smsEnablerSearch.value, options = {}) {
	if (!smsEnablerAvailable.value || props.isOffline) {
		return
	}

	loadingSmsEnablerPayments.value = true

	try {
		const result = await call("pos_next.api.smsenabler_mpesa.get_sms_payments", {
			company: props.company,
			pos_profile: props.posProfile,
			search,
			amount: options.suggest ? remainingAmount.value : 0,
			customer: props.customer?.name || props.customer,
		})

		const availablePayments = (result?.payments || []).filter(
			(payment) =>
				payment?.status === "Pending" &&
				!payment?.sales_invoice &&
				!payment?.payment_entry,
		)
		smsEnablerPendingCount.value = availablePayments.length
		smsEnablerPayments.value = availablePayments

		if (options.suggest && isAutoSmsReconciliation.value) {
			autoApplySmsEnablerMatch()
		}
	} catch (error) {
		console.error("[PaymentDialog] Failed to load SMS Enabler payments:", error)
		showError(error.message || __("Failed to load SMS Enabler payments"))
	} finally {
		loadingSmsEnablerPayments.value = false
	}
}

function toggleSmsEnablerPanel() {
	showSmsEnablerPanel.value = !showSmsEnablerPanel.value

	if (showSmsEnablerPanel.value) {
		loadSmsEnablerPayments("", {
			suggest: isSuggestedSmsReconciliation.value || isAutoSmsReconciliation.value,
		})
	}
}

function handleSmsEnablerSearchInput() {
	if (smsEnablerSearchTimeout) {
		clearTimeout(smsEnablerSearchTimeout)
	}

	const search = smsEnablerSearch.value.trim()

	smsEnablerSearchTimeout = setTimeout(() => {
		loadSmsEnablerPayments(search, {
			suggest: search.length === 0 && (isSuggestedSmsReconciliation.value || isAutoSmsReconciliation.value),
		})
	}, 300)
}

function isSmsEnablerSelected(paymentName) {
	return selectedSmsEnablerPayments.value.some((payment) => payment.name === paymentName)
}

function isSmsEnablerAlreadyAdded(paymentName) {
	return paymentEntries.value.some((entry) => entry.is_sms_enabler && entry.sms_payment_name === paymentName)
}

function addSmsEnablerPayment(payment) {
	if (!payment || isSmsEnablerAlreadyAdded(payment.name)) {
		return
	}

	if (!smsEnablerModeOfPayment.value) {
		showError(__("No Phone mode of payment is configured for SMS payments"))
		return
	}

	const amount = Number.parseFloat(payment.amount || 0)
	if (!amount || amount <= 0) {
		return
	}

	paymentEntries.value.push({
		mode_of_payment: payment.mode_of_payment || smsEnablerModeOfPayment.value,
		amount,
		type: "Phone",
		is_sms_enabler: true,
		sms_payment_name: payment.name,
		sms_transaction_id: payment.transaction_id || payment.name,
		reference_no: payment.transaction_id || payment.name,
	})
}

function removeSmsEnablerPayment(paymentName) {
	paymentEntries.value = paymentEntries.value.filter(
		(entry) => !(entry.is_sms_enabler && entry.sms_payment_name === paymentName),
	)
}

function toggleSmsEnablerPayment(payment) {
	if (isSmsEnablerAlreadyAdded(payment.name)) {
		removeSmsEnablerPayment(payment.name)
		return
	}

	addSmsEnablerPayment(payment)
}

function addSelectedSmsEnablerPayments() {
	selectedSmsEnablerPayments.value.forEach((payment) => addSmsEnablerPayment(payment))
	selectedSmsEnablerPayments.value = []
}

function autoApplySmsEnablerMatch() {
	if (smsEnablerAutoApplied.value || remainingAmount.value <= 0) {
		return
	}

	const highConfidenceMatches = smsEnablerPayments.value.filter(
		(payment) =>
			payment.match_level === "High" &&
			payment.is_exact_amount &&
			!isSmsEnablerAlreadyAdded(payment.name),
	)

	if (highConfidenceMatches.length !== 1) {
		return
	}

	addSmsEnablerPayment(highConfidenceMatches[0])
	smsEnablerAutoApplied.value = true
	showSuccess(__("SMS Enabler payment matched automatically"))
}

// Currency symbol for display
const currencySymbol = computed(() => getCurrencySymbol(props.currency))

// Helper to round to 2 decimal places (handles floating-point precision)
const round2 = (val) => Number(Number(val).toFixed(2))

const totalPaid = computed(() => {
	const sum = paymentEntries.value.reduce(
		(sum, entry) => sum + getPaymentAmount(entry),
		0,
	)
	return round2(sum)
})

const totalAvailableCredit = computed(() => {
	// Use net_balance: negative means customer has credit, positive means they owe
	// Return negative of net_balance so positive = credit available, negative = outstanding
	return round2(-customerBalance.value.net_balance)
})

const selectedMpesaTotal = computed(() => {
	return round2(
		selectedMpesaPayments.value.reduce(
			(sum, payment) => sum + (Number.parseFloat(payment.transamount) || 0),
			0,
		),
	)
})

const mpesaStkAmount = computed(() => {
	return remainingAmount.value > 0 ? remainingAmount.value : round2(props.grandTotal)
})

const selectedSmsEnablerTotal = computed(() => {
	return round2(
		selectedSmsEnablerPayments.value.reduce(
			(sum, payment) => sum + (Number.parseFloat(payment.amount) || 0),
			0,
		),
	)
})

const appliedMpesaPayments = computed(() =>
	paymentEntries.value.filter((entry) => entry.is_mpesa && entry.mpesa_payment_name),
)

const appliedMpesaPaymentCount = computed(() => appliedMpesaPayments.value.length)

const appliedMpesaTotal = computed(() =>
	round2(appliedMpesaPayments.value.reduce((sum, entry) => sum + (entry.amount || 0), 0)),
)

const appliedSmsEnablerPayments = computed(() =>
	paymentEntries.value.filter((entry) => entry.is_sms_enabler && entry.sms_payment_name),
)

const appliedSmsEnablerPaymentCount = computed(() => appliedSmsEnablerPayments.value.length)

const appliedSmsEnablerTotal = computed(() =>
	round2(appliedSmsEnablerPayments.value.reduce((sum, entry) => sum + (entry.amount || 0), 0)),
)

const smsReconciliationMode = computed(
	() => settingsStore.smsPaymentReconciliationMode || "Manual",
)

const isSuggestedSmsReconciliation = computed(
	() => smsReconciliationMode.value === "Suggested",
)

const isAutoSmsReconciliation = computed(
	() => smsReconciliationMode.value === "Auto",
)

const addedMpesaNames = computed(() => {
	return paymentEntries.value
		.filter((entry) => entry.is_mpesa && entry.mpesa_payment_name)
		.map((entry) => entry.mpesa_payment_name)
})

const remainingAmount = computed(() => {
	const remaining = round2(props.grandTotal) - totalPaid.value
	return remaining > 0 ? round2(remaining) : 0
})

const changeAmount = computed(() => {
	const change = totalPaid.value - round2(props.grandTotal)
	return change > 0 ? round2(change) : 0
})

const canComplete = computed(() => {
	const hasPositivePayment = paymentEntries.value.some(
		(entry) => getPaymentAmount(entry) > 0,
	)

	// If partial payment is allowed, can complete with any amount > 0
	if (props.allowPartialPayment) {
		return totalPaid.value > 0 && hasPositivePayment
	}
	// Otherwise require full payment
	return remainingAmount.value === 0 && hasPositivePayment
})

const paymentButtonText = computed(() => {
	if (remainingAmount.value === 0) {
		return __("Complete Payment")
	}
	if (props.allowPartialPayment && totalPaid.value > 0) {
		return __("Partial Payment")
	}
	return __("Complete Payment")
})

const quickAmounts = computed(() => {
	const remaining = remainingAmount.value
	if (remaining <= 0) {
		return [10, 20, 50, 100]
	}

	const amounts = new Set()
	const exactAmount = Math.ceil(remaining)

	// Always include exact amount first
	amounts.add(exactAmount)

	// Determine appropriate denominations based on amount size
	// For amounts < 50, use smaller denominations
	// For amounts >= 50, skip to larger denominations for meaningful differences
	let denominations
	if (remaining < 20) {
		denominations = [5, 10, 20, 50]
	} else if (remaining < 100) {
		denominations = [10, 20, 50, 100]
	} else if (remaining < 500) {
		denominations = [50, 100, 200, 500]
	} else if (remaining < 2000) {
		denominations = [100, 200, 500, 1000]
	} else {
		denominations = [500, 1000, 2000, 5000]
	}

	// Minimum gap between suggestions (at least 5% or 5, whichever is larger)
	const minGap = Math.max(5, exactAmount * 0.05)

	// Helper to check if amount is far enough from existing amounts
	const isFarEnough = (newAmt) => {
		for (const existing of amounts) {
			if (Math.abs(newAmt - existing) < minGap) return false
		}
		return true
	}

	// Add round-up amounts for each denomination
	for (const denom of denominations) {
		if (amounts.size >= 4) break

		// Round up to next multiple of this denomination
		const roundedUp = Math.ceil(remaining / denom) * denom

		// Add if it's meaningfully different from exact amount
		if (roundedUp > exactAmount && isFarEnough(roundedUp)) {
			amounts.add(roundedUp)
		}

		// Also add one step higher for convenience (e.g., 350 when remaining is 299)
		if (amounts.size < 4) {
			const oneStepUp = roundedUp + denom
			if (oneStepUp > exactAmount && isFarEnough(oneStepUp)) {
				amounts.add(oneStepUp)
			}
		}
	}

	// Convert to array, sort, and limit to 4
	return Array.from(amounts)
		.filter((amt) => amt > 0)
		.sort((a, b) => a - b)
		.slice(0, 4)
})

// Preload payment methods when posProfile is set (before dialog opens)
watch(
	() => props.posProfile,
	(newProfile) => {
		if (newProfile) {
			console.log('[PaymentDialog] Preloading payment methods for profile:', newProfile)
			loadPaymentMethods()
			// Also preload sales persons if enabled
			if (settingsStore.enableSalesPersons && salesPersons.value.length === 0) {
				loadingSalesPersons.value = true
				salesPersonsResource.fetch()
			}
		}
	},
	{ immediate: true } // Load immediately if posProfile is already set
)

watch(show, (newVal) => {
	if (newVal) {
		// Reset state when dialog opens
		stopMpesaStkPolling()
		paymentEntries.value = []
		customAmount.value = ""
		lastSelectedMethod.value = null
		customerCredit.value = []
		customerBalance.value = { total_outstanding: 0, total_credit: 0, net_balance: 0 }
		selectedSalesPersons.value = []
		salesPersonSearch.value = ''
		showMpesaPanel.value = false
		mpesaSearch.value = ""
		mpesaPayments.value = []
		mpesaPendingCount.value = 0
		selectedMpesaPayments.value = []
		mpesaStkPhone.value = ""
		mpesaStkRequest.value = null
		mpesaStkMatch.value = null
		mpesaStkStatusMessage.value = ""
		mpesaStkPollAttempts.value = 0
		showSmsEnablerPanel.value = false
		smsEnablerSearch.value = ""
		smsEnablerPayments.value = []
		smsEnablerPendingCount.value = 0
		selectedSmsEnablerPayments.value = []
		smsEnablerAutoApplied.value = false

		// Debug logging
		console.log('[PaymentDialog] Dialog opened with props:', {
			allowCreditSale: props.allowCreditSale,
			customer: props.customer,
			company: props.company,
			posProfile: props.posProfile
		})

		// Set default payment method if already loaded
		if (paymentMethods.value.length > 0 && !lastSelectedMethod.value) {
			const defaultMethod = paymentMethods.value.find((m) => m.default)
			lastSelectedMethod.value = defaultMethod || paymentMethods.value[0]
		}

		// Load customer credit and balance if enabled and customer is selected
		if (props.allowCreditSale && props.customer && props.company) {
			console.log('[PaymentDialog] Loading customer credit and balance...')
			loadingCredit.value = true
			customerCreditResource.fetch()
			customerBalanceResource.fetch()
		} else {
			console.log('[PaymentDialog] Not loading credit because:', {
				allowCreditSale: props.allowCreditSale,
				hasCustomer: !!props.customer,
				hasCompany: !!props.company
			})
		}

		checkMpesaAvailability()
		checkSmsEnablerAvailability()
	}
})

onUnmounted(() => {
	stopMpesaStkPolling()
	if (mpesaSearchTimeout) {
		clearTimeout(mpesaSearchTimeout)
	}
	if (smsEnablerSearchTimeout) {
		clearTimeout(smsEnablerSearchTimeout)
	}
})

// One-click payment - adds remaining amount with selected method
function quickAddPayment(method) {
	console.log('[PaymentDialog] Quick add payment:', {
		method: method.mode_of_payment,
		remainingAmount: remainingAmount.value,
		currentEntries: paymentEntries.value.length
	})

	lastSelectedMethod.value = method
	const amount = remainingAmount.value > 0
		? Number.parseFloat(remainingAmount.value.toFixed(2))
		: 0

	paymentEntries.value.push({
		mode_of_payment: method.mode_of_payment,
		amount,
		type: method.type || __('Cash'),
		reference_no: "",
	})

	console.log('[PaymentDialog] Payment added, new entries:', paymentEntries.value)
	customAmount.value = ""
}

// Add custom amount for a method
function addCustomPayment(method, amount) {
	console.log('[PaymentDialog] Add custom payment:', {
		method: method.mode_of_payment,
		amount: amount,
		currentEntries: paymentEntries.value.length
	})

	const amt = Number.parseFloat(amount)
	if (!amt || amt <= 0) return

	paymentEntries.value.push({
		mode_of_payment: method.mode_of_payment,
		amount: amt,
		type: method.type || __('Cash'),
		reference_no: "",
	})

	console.log('[PaymentDialog] Payment added, new entries:', paymentEntries.value)
	customAmount.value = ""
}

// Apply existing customer credit to payment
function applyCustomerCredit() {
	console.log('[PaymentDialog] Apply customer credit:', {
		totalCredit: totalAvailableCredit.value,
		remainingAmount: remainingAmount.value,
		currentEntries: paymentEntries.value.length
	})

	if (remainingAmount.value === 0 || totalAvailableCredit.value === 0) return

	// Calculate how much credit to apply (min of remaining amount and available credit)
	const creditToApply = Math.min(remainingAmount.value, totalAvailableCredit.value)

	// Add credit as a payment entry
	paymentEntries.value.push({
		mode_of_payment: "Customer Credit",
		amount: Number.parseFloat(creditToApply.toFixed(2)),
		type: "Credit",
		is_customer_credit: true,
		credit_details: customerCredit.value.map(credit => ({
			...credit,
			credit_to_redeem: 0  // Will be calculated on backend
		}))
	})

	console.log('[PaymentDialog] Existing credit applied, new entries:', paymentEntries.value)
}

// Add "Pay on Account" - Credit Sale (invoice with outstanding amount)
function addCreditAccountPayment() {
	console.log('[PaymentDialog] Add credit account payment (Pay Later):', {
		grandTotal: props.grandTotal,
		currentPaid: totalPaid.value,
		remainingAmount: remainingAmount.value
	})

	// Close dialog and complete as credit sale (0 payment)
	// The backend will create an invoice with outstanding amount
	const paymentData = {
		payments: [],  // No payments - full amount on credit
		change_amount: 0,
		is_partial_payment: false,
		is_credit_sale: true,  // Mark as credit sale
		paid_amount: 0,
		outstanding_amount: props.grandTotal,
	}

	console.log('[PaymentDialog] Emitting credit sale payment-completed:', paymentData)
	emit("payment-completed", paymentData)
	show.value = false
}

function removePaymentEntry(index) {
	paymentEntries.value.splice(index, 1)
}

function getPaymentAmount(entry) {
	const amount = Number.parseFloat(entry?.amount)
	return Number.isFinite(amount) && amount > 0 ? amount : 0
}

function isPaymentEntryLocked(entry) {
	return Boolean(
		(entry?.is_mpesa && entry?.mpesa_payment_name) ||
		(entry?.is_sms_enabler && entry?.sms_payment_name),
	)
}

function canEditPaymentDetails(entry) {
	return Boolean(entry) && !entry.is_customer_credit && !isPaymentEntryLocked(entry)
}

function normalizePaymentReference(index) {
	const entry = paymentEntries.value[index]
	if (!canEditPaymentDetails(entry)) {
		return
	}

	entry.reference_no = String(entry.reference_no || "").trim()
}

function updatePaymentMethod(index, modeOfPayment) {
	const entry = paymentEntries.value[index]
	if (!entry || isPaymentEntryLocked(entry)) {
		return
	}

	const method = paymentMethods.value.find(
		(method) => method.mode_of_payment === modeOfPayment,
	)
	if (method) {
		entry.mode_of_payment = method.mode_of_payment
		entry.type = method.type || __("Cash")
	}
}

function normalizePaymentAmount(index) {
	const entry = paymentEntries.value[index]
	if (!canEditPaymentDetails(entry)) {
		return
	}

	const amount = Number.parseFloat(entry.amount)
	entry.amount = Number.isFinite(amount) && amount > 0 ? round2(amount) : 0
}

function clearAll() {
	paymentEntries.value = []
	customAmount.value = ""
}

function getValidPaymentEntries() {
	return paymentEntries.value
		.map((entry) => ({
			...entry,
			amount: getPaymentAmount(entry),
		}))
		.filter((entry) => entry.mode_of_payment && entry.amount > 0)
}

function completePayment() {
	console.log('[PaymentDialog] Complete payment called:', {
		canComplete: canComplete.value,
		totalPaid: totalPaid.value,
		grandTotal: props.grandTotal,
		allowPartialPayment: props.allowPartialPayment,
		paymentEntries: paymentEntries.value,
		salesPersons: selectedSalesPersons.value
	})

	if (!canComplete.value) {
		console.warn('[PaymentDialog] Cannot complete - validation failed')
		return
	}

	const isPartial = totalPaid.value < props.grandTotal
	const validPaymentEntries = getValidPaymentEntries()

	const paymentData = {
		payments: validPaymentEntries,
		change_amount: changeAmount.value,
		is_partial_payment: isPartial,
		paid_amount: totalPaid.value,
		outstanding_amount: isPartial ? remainingAmount.value : 0,
		sales_team: selectedSalesPersons.value.length > 0 ? selectedSalesPersons.value : null,
		mpesa_payments: validPaymentEntries
			.filter((entry) => entry.is_mpesa && entry.mpesa_payment_name)
			.map((entry) => ({
				name: entry.mpesa_payment_name,
				transaction_id: entry.mpesa_transaction_id,
				amount: entry.amount,
				mode_of_payment: entry.mode_of_payment,
			})),
		sms_enabler_payments: validPaymentEntries
			.filter((entry) => entry.is_sms_enabler && entry.sms_payment_name)
			.map((entry) => ({
				name: entry.sms_payment_name,
				transaction_id: entry.sms_transaction_id,
				amount: entry.amount,
				mode_of_payment: entry.mode_of_payment,
			})),
	}

	console.log('[PaymentDialog] Emitting payment-completed:', paymentData)

	emit("payment-completed", paymentData)

	show.value = false
}

function formatCurrency(amount) {
	return formatCurrencyUtil(Number.parseFloat(amount || 0), props.currency)
}

// Get total amount for a specific payment method
function getMethodTotal(methodName) {
	return paymentEntries.value
		.filter((entry) => entry.mode_of_payment === methodName)
		.reduce((sum, entry) => sum + getPaymentAmount(entry), 0)
}


// Additional discount handlers
function handleAdditionalDiscountChange() {
	let discountValue = localAdditionalDiscount.value
	let discountAmount = 0

	// If percentage mode, calculate amount
	if (additionalDiscountType.value === 'percentage') {
		// Validate against max_discount_allowed if configured
		if (settingsStore.maxDiscountAllowed > 0 && discountValue > settingsStore.maxDiscountAllowed) {
			localAdditionalDiscount.value = settingsStore.maxDiscountAllowed
			discountValue = settingsStore.maxDiscountAllowed
			// Show warning toast
			showWarning(__('Maximum allowed discount is {0}%', [settingsStore.maxDiscountAllowed]))
		}

		// Ensure percentage is between 0-100
		if (discountValue > 100) {
			localAdditionalDiscount.value = 100
			discountValue = 100
		}

		// Convert percentage to amount
		discountAmount = (props.subtotal * discountValue) / 100
	} else {
		// Amount mode
		discountAmount = discountValue

		// For amount mode, check if it exceeds percentage limit when converted
		if (settingsStore.maxDiscountAllowed > 0 && props.subtotal > 0) {
			const percentageEquivalent = (discountAmount / props.subtotal) * 100
			if (percentageEquivalent > settingsStore.maxDiscountAllowed) {
				const maxAmount = (props.subtotal * settingsStore.maxDiscountAllowed) / 100
				localAdditionalDiscount.value = maxAmount
				discountAmount = maxAmount
				// Show warning toast
				showWarning(__('Maximum allowed discount is {0}% ({1} {2})',
				[settingsStore.maxDiscountAllowed, props.currency, maxAmount.toFixed(2)]))
			}
		}
	}

	// Ensure discount doesn't exceed subtotal
	if (discountAmount > props.subtotal) {
		if (additionalDiscountType.value === 'amount') {
			localAdditionalDiscount.value = props.subtotal
		}
		discountAmount = props.subtotal
	}

	// Ensure non-negative
	if (discountAmount < 0) {
		localAdditionalDiscount.value = 0
		discountAmount = 0
	}

	emit("update-additional-discount", discountAmount)
}

function handleAdditionalDiscountTypeChange() {
	// Don't reset - preserve last value when toggling type
	// Just recalculate to ensure it's within limits
	handleAdditionalDiscountChange()
}

function clearAdditionalDiscount() {
	localAdditionalDiscount.value = 0
	emit("update-additional-discount", 0)
}

// Watch for dialog open to sync additional discount from parent
watch(
	() => props.modelValue,
	(isOpen) => {
		if (isOpen) {
			// Only sync when dialog opens, not continuously
			localAdditionalDiscount.value = props.additionalDiscount || 0
		}
	},
)
</script>

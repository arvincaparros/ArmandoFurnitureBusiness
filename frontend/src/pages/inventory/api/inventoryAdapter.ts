import type {
  InventoryOverviewResponse,
  ProductInventoryResponse,
} from './inventoryTypes'

import type {
  InventoryOverview,
  ProductInventory,
} from '../types'

// Same Decimal-as-JSON-string convention as every other adapter in
// this codebase (see transaction-history/api/transactionAdapter.ts) -
// duplicated locally rather than imported, matching the per-module
// convention.
function parseDecimal(value: string): number {
  const parsed = Number(value)

  return Number.isFinite(parsed) ? parsed : 0
}

function toUiProductInventory(
  row: ProductInventoryResponse,
): ProductInventory {
  return {
    productId: row.product_id,
    productName: row.product_name,
    openingQuantity: parseDecimal(row.opening_quantity),
    totalProduced: parseDecimal(row.total_produced),
    totalSold: parseDecimal(row.total_sold),
    availableStock: parseDecimal(row.available_stock),
    cycleProduced: parseDecimal(row.cycle_produced),
    cycleSold: parseDecimal(row.cycle_sold),
  }
}

export function toUiInventory(
  response: InventoryOverviewResponse,
): InventoryOverview {
  return {
    cycleId: response.cycle_id,
    cycleStartDate: response.cycle_start_date,
    cycleEndDate: response.cycle_end_date,
    stockValidationEnabled: response.stock_validation_enabled,
    products: response.products.map(toUiProductInventory),
  }
}

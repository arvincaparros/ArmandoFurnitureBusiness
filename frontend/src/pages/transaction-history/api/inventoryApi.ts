import apiClient from '../../../api/client'

// Minimal local slice of GET /api/inventory - only what this page
// needs to show available stock and the auto-filled produced figure.
// Same local-copy convention already used by this page's
// ProductSummary and by production-allocation/api/productionTypes.ts.
export interface InventorySliceRow {
  product_id: number
  available_stock: string
  cycle_produced: string
}

export interface InventorySliceResponse {
  stock_validation_enabled: boolean
  products: InventorySliceRow[]
}

export async function fetchInventorySlice(): Promise<
  InventorySliceResponse
> {
  const response = await apiClient.get<InventorySliceResponse>(
    '/api/inventory',
  )

  return response.data
}

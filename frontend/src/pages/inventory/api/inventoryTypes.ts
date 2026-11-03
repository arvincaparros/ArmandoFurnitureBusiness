// Mirrors backend/app/schemas/inventory.py exactly. Every Decimal
// field arrives as a JSON string, never a bare number - the same
// convention as every other Decimal field in this backend.

export interface ProductInventoryResponse {
  product_id: number
  product_name: string
  opening_quantity: string
  total_produced: string
  total_sold: string
  available_stock: string
  cycle_produced: string
  cycle_sold: string
}

export interface InventoryOverviewResponse {
  cycle_id: number | null
  cycle_start_date: string | null
  cycle_end_date: string | null
  // False until an opening inventory set has been reviewed. While
  // false the backend does NOT enforce stock on sales, so the UI must
  // say so rather than implying the numbers are being enforced.
  stock_validation_enabled: boolean
  products: ProductInventoryResponse[]
}

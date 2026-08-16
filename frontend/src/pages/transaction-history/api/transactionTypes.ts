// Mirrors backend/app/schemas/transaction.py exactly. transaction_number
// is server-generated (see app/services/transaction.py::
// generate_transaction_number) - it has no counterpart in the create
// request. All Decimal fields arrive as JSON strings, never bare
// numbers, matching every other Decimal field in this backend.

export interface SalesTransactionResponse {
  id: number
  transaction_number: string
  product_id: number
  transaction_date: string
  quantity_produced: string
  quantity: string
  unit_price: string
  total_sales: string
  production_cost: string
  unit_profit: string
  total_profit: string
  created_at: string
}

// unit_price is required here - the backend computes total_sales as
// quantity * unit_price server-side (app/services/transaction.py::
// calculate_transaction_values); there is no field to submit a raw
// sales amount directly. Decimal inputs are sent as JS numbers, same
// convention as ProductResourceRequirementCreateRequest.
export interface SalesTransactionCreateRequest {
  product_id: number
  transaction_date: string
  quantity_produced: number
  quantity: number
  unit_price: number
  production_cost: number
}

// Mirrors backend/app/schemas/transaction.py's SalesTransactionUpdate
// exactly - deliberately has no product_id field. The backend does
// not accept reassigning a transaction to a different product on
// update; the frontend must not attempt to send one.
export interface SalesTransactionUpdateRequest {
  transaction_date?: string
  quantity_produced?: number
  quantity?: number
  unit_price?: number
  production_cost?: number
}

// Minimal slice of GET /api/products - only what's needed to resolve
// product_id -> name (table display, create-form dropdown) - same
// local-copy pattern already used in dashboard/api/dashboardTypes.ts
// and production-allocation/api/productionTypes.ts.
export interface ProductSummary {
  id: number
  name: string
  selling_price: string
}

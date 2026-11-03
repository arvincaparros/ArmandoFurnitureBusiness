// Mirrors backend/app/schemas/opening_inventory.py exactly.

export interface OpeningInventoryItemResponse {
  id: number
  product_id: number
  quantity: string
  notes: string | null
}

export interface OpeningInventorySetResponse {
  id: number
  set_number: string
  // "DRAFT" | "REVIEWED" | "SUPERSEDED" - see
  // app/services/opening_inventory.py for the only values written.
  status: string
  effective_date: string
  notes: string | null
  created_at: string
  reviewed_at: string | null
  created_by_username: string | null
  reviewed_by_username: string | null
  items: OpeningInventoryItemResponse[]
}

export interface OpeningInventoryStatusResponse {
  stock_validation_enabled: boolean
  reviewed_set: OpeningInventorySetResponse | null
  draft_set: OpeningInventorySetResponse | null
}

// Decimal inputs are sent as JS numbers, same convention as
// SalesTransactionCreateRequest.
export interface OpeningInventoryItemInput {
  product_id: number
  quantity: number
  notes?: string | null
}

export interface OpeningInventorySetCreateRequest {
  effective_date: string
  notes?: string | null
  items: OpeningInventoryItemInput[]
}

// items, when sent, REPLACES the whole list - the backend has no
// per-item merge, deliberately (see OpeningInventorySetUpdate).
export interface OpeningInventorySetUpdateRequest {
  effective_date?: string
  notes?: string | null
  items?: OpeningInventoryItemInput[]
}

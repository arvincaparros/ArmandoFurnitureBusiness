// Mirrors backend/app/schemas/product.py exactly. labor_cost is the
// client cost-model reconciliation addition (Phase 1) - a per-product
// value, NOT derived from labor hours x a shared resource rate (see
// productAdapter.ts). None of the resource-usage quantities (wood/
// epoxy/nails/...), machine/labor hours, material cost, or machine
// cost live on this record - those still come from
// ProductResourceRequirement + CycleResource.

export interface ProductResponse {
  id: number
  name: string
  selling_price: string
  labor_cost: string
  // Always present - the column is NOT NULL and ProductResponse
  // declares it required, so this is never optional on a response.
  // Serialized as a Decimal string like "3.0000" even though only
  // whole units are accepted on the way in (see productAdapter.ts,
  // which parses it back to an integer).
  minimum_demand: string
  is_active: boolean
}

// Requests may send selling_price/labor_cost as plain JSON numbers -
// Pydantic parses numeric JSON into Decimal directly, so no string
// formatting is needed on the way out (only responses serialize
// Decimal as a string).
export interface ProductCreateRequest {
  name: string
  selling_price: number
  labor_cost: number
  // Optional, defaulting to 0 server-side when omitted. Whole units
  // only - the backend rejects negative, fractional, and
  // above-1,000,000 values with a 422.
  minimum_demand?: number
  is_active?: boolean
}

export interface ProductUpdateRequest {
  name?: string
  selling_price?: number
  labor_cost?: number
  // Omitted means "leave unchanged"; an explicit 0 is a real value
  // ("no minimum") and IS persisted as 0.
  minimum_demand?: number
  is_active?: boolean
}

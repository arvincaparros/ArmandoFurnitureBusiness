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
  is_active?: boolean
}

export interface ProductUpdateRequest {
  name?: string
  selling_price?: number
  labor_cost?: number
  is_active?: boolean
}

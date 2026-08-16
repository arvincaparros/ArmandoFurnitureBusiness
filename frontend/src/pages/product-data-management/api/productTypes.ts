// Mirrors backend/app/schemas/product.py exactly. The global Product
// record has only these four fields - none of the resource-usage
// quantities (wood/epoxy/nails/...), machine/labor hours, or cost/
// profit figures the frontend's mock data implied exist here. See
// the Phase 6 integration report for why those are NOT included.

export interface ProductResponse {
  id: number
  name: string
  selling_price: string
  is_active: boolean
}

// Requests may send selling_price as a plain JSON number - Pydantic
// parses numeric JSON into Decimal directly, so no string formatting
// is needed on the way out (only responses serialize Decimal as a
// string).
export interface ProductCreateRequest {
  name: string
  selling_price: number
  is_active?: boolean
}

export interface ProductUpdateRequest {
  name?: string
  selling_price?: number
  is_active?: boolean
}

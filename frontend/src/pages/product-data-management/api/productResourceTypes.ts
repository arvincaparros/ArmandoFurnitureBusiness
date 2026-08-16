// Mirrors backend/app/schemas/product.py's ProductResourceRequirement*
// schemas exactly. Note the response has no resource name/type/unit -
// only a bare resource_id. See ResourceOption below and
// productResourceAdapter.ts for how display info is resolved.

export interface ProductResourceRequirementResponse {
  id: number
  product_id: number
  resource_id: number
  quantity_required: string
}

export interface ProductResourceRequirementCreateRequest {
  resource_id: number
  quantity_required: number
}

export interface ProductResourceRequirementUpdateRequest {
  quantity_required: number
}

// Mirrors backend/app/schemas/resource.py's ResourceResponse -
// local to this module rather than imported from
// resources-management/api, matching the existing project
// convention (Dashboard and Production each keep their own local
// copy of cross-module response shapes rather than importing
// another page's api folder).
export interface ResourceOption {
  id: number
  name: string
  resource_type: string
  unit: string
  is_active: boolean
}

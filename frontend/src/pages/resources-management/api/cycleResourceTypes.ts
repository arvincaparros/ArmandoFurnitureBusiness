// Local mirror of backend/app/schemas/production.py's CycleResource*
// schemas - kept local to this module (not imported from
// product-data-management/api) per this project's convention of
// duplicating small cross-module response/request shapes rather than
// importing another page's api folder.

export interface CycleResourceResponse {
  id: number
  production_cycle_id: number
  resource_id: number
  available_quantity: string
  unit_price: string
}

export interface CycleResourceCreateRequest {
  resource_id: number
  available_quantity: number
  unit_price: number
}

export interface CycleResourceUpdateRequest {
  available_quantity?: number
  unit_price?: number
}

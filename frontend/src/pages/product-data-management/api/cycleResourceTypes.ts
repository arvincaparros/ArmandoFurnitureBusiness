// Local mirror of backend/app/schemas/production.py's
// CycleResourceResponse - kept local to this module (not imported
// from resources-management/api) per this project's convention of
// duplicating small cross-module response shapes. Only the fields
// this module needs for cost calculation are declared.

export interface CycleResourceResponse {
  id: number
  production_cycle_id: number
  resource_id: number
  available_quantity: string
  unit_price: string
}

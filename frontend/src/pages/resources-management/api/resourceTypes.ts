// Mirrors backend/app/schemas/resource.py exactly. Notably absent:
// available_quantity, unit_price, total_value - those live on
// CycleResource (backend/app/database/models.py), scoped to a
// specific production_cycle_id, not on this global Resource record.
// See the Phase 5 integration report for why they are NOT included
// here rather than invented.

export interface ResourceResponse {
  id: number
  name: string
  resource_type: string
  unit: string
  is_active: boolean
}

export interface ResourceCreateRequest {
  name: string
  resource_type: string
  unit: string
  is_active?: boolean
}

export interface ResourceUpdateRequest {
  name?: string
  resource_type?: string
  unit?: string
  is_active?: boolean
}

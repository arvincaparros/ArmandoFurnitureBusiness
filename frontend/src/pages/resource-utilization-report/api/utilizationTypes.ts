// Mirrors backend/app/schemas/utilization.py exactly.

export interface ResourceUtilizationItem {
  resource_id: number
  resource_name: string
  resource_type: string
  unit: string
  available_quantity: string
  consumed_quantity: string
  remaining_quantity: string
  utilization_rate: string
  // "normal" | "high" | "at_risk" | "bottleneck" - see
  // ../utilizationStatus.ts for the display mapping.
  status: string
}

export interface ResourceUtilizationBottleneck {
  resource_id: number
  resource_name: string
  unit: string
  remaining_quantity: string
  is_binding: boolean
  shortage_quantity: string
}

export interface ResourceUtilizationResponse {
  cycle_id: number

  // Retained by the backend for compatibility only - both blend
  // incompatible units (kg + hours + pcs) into one ratio/quantity.
  // Intentionally NOT read by utilizationAdapter.ts anymore; kept
  // here only because they're still present on the wire.
  overall_utilization_rate: string
  total_raw_materials_consumed: string

  total_labor_hours_used: string
  total_labor_hours_capacity: string
  total_machine_hours_used: string
  total_machine_hours_capacity: string

  material_resource_count: number
  most_constrained_resource: ResourceUtilizationItem | null
  at_risk_resources: ResourceUtilizationItem[]

  resources: ResourceUtilizationItem[]
  bottlenecks: ResourceUtilizationBottleneck[]
}

// Local, minimal copy of the production-cycles list shape - kept
// self-contained rather than imported from production-allocation's
// api folder, matching the existing per-module convention (Dashboard
// and Production each keep their own local copies too).
export interface ProductionCycleResponse {
  id: number
}

// Mirrors backend/app/schemas/utilization.py's
// ResourceUtilizationRunSummaryResponse/ResourceUtilizationRunResponse/
// ResourceUtilizationHistoryItemResponse exactly. Distinct from
// ResourceUtilizationItem in resource-utilization-report/api/
// utilizationTypes.ts - these fields are an immutable snapshot taken
// when "Apply to Production" succeeded, never a live recalculation.

export interface ResourceUtilizationRunSummaryResponse {
  id: number
  utilization_number: string
  production_cycle_id: number
  generated_at: string
  resource_count: number
  bottleneck_count: number
  at_risk_count: number
}

export interface ResourceUtilizationHistoryItemResponse {
  id: number
  resource_id: number | null
  resource_name: string
  resource_type: string
  unit: string
  available_quantity: string
  consumed_quantity: string
  remaining_quantity: string
  utilization_rate: string
  status: string
}

export interface ResourceUtilizationRunResponse {
  id: number
  utilization_number: string
  production_cycle_id: number
  generated_at: string
  items: ResourceUtilizationHistoryItemResponse[]
}

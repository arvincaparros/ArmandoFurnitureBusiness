import type { PlanningMode } from './api/productionTypes'

export interface ProductionPlan {
  id: number
  productName: string
  quantity: number

  // Revision #2 financial breakdown. totalRevenue is never null -
  // Product.selling_price is a required, always-positive backend
  // field. totalCost/totalProfit ARE nullable for Current Production
  // Allocation rows only (see productionAdapter.ts::fromAllocations) -
  // null means a required non-labor resource is currently inactive or
  // unpriced, so cost/profit can't be reliably calculated and must
  // not be silently shown as 0 (Revision #1's rule). Production Plan
  // rows (fromOptimizeResponse/fromHistoryRun) never produce null
  // here - see the Revision #2 report's note on the optimizer's own
  // still-unfixed silent-zero behavior.
  totalRevenue: number
  totalCost: number | null
  totalProfit: number | null

  // Adaptive minimum demand (v2 plan). null for Current Production
  // Allocation rows (fromAllocations) - the backend's applied-
  // allocation endpoint (ProductionAllocationFinancialsResponse)
  // genuinely has no minimum_demand/shortfall fields at all, unlike
  // the fresh-optimize and history endpoints, which both already
  // carry them. Never fabricated as 0 for that row shape.
  minimumDemand: number | null
  shortfall: number | null
}

// One row of the Resource Utilization Summary preview card - THIS
// Generate result's own proposed usage, never blended with an
// earlier Generate's figures. See productionAdapter.ts::
// fromOptimizeResponse and productionTypes.ts::
// OptimizationResourceUsage's own notes.
export interface ResourceUtilizationRow {
  resourceId: number
  resourceName: string
  unit: string
  consumed: number
  remaining: number
  utilizationRate: number
  status: string
}

export interface OptimizationSummary {
  totalRevenue: number
  totalCost: number
  totalProfit: number

  startTime: string
  endTime: string
  duration: string

  // Set only on a fresh Generate result (fromOptimizeResponse); null
  // for a persisted/history-sourced result, since planning_mode is
  // not persisted on the backend - see productionTypes.ts's own note.
  planningMode: PlanningMode | null

  // Set only on a fresh Generate result - [] for a persisted/
  // history-sourced result, since resource_usage is computed
  // transiently at Generate time and never persisted (same reason
  // planningMode is null there). An empty array means "no fresh
  // preview available this session," not "this plan consumes
  // nothing."
  resourceUsage: ResourceUtilizationRow[]
}
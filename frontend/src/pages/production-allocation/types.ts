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

export interface OptimizationSummary {
  totalRevenue: number
  totalCost: number
  totalProfit: number

  startTime: string
  endTime: string
  duration: string
}
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
}

export interface OptimizationSummary {
  totalRevenue: number
  totalCost: number
  totalProfit: number

  startTime: string
  endTime: string
  duration: string
}
export interface OptimizationHistory {
  id: number
  optimizationId: string
  dateGenerated: string
  duration: number
  totalProfit: number
  // null when the backend doesn't provide a cost figure for this run
  // (GET /api/optimization/history has no total-cost field) - never a
  // fabricated 0. See optimizationHistoryAdapter.ts.
  totalProductionCost: number | null
  productsProduced: number
}

export interface ProfitTrend {
  optimizationId: string
  profit: number
}
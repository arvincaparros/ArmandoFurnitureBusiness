export interface OptimizationHistory {
  id: number
  optimizationId: string
  dateGenerated: string
  duration: number
  totalProfit: number
  // null only for a run saved before total_cost was tracked - never
  // backfilled from current prices. See optimizationHistoryAdapter.ts.
  totalProductionCost: number | null
  productsProduced: number
}

export interface ProfitTrend {
  optimizationId: string
  profit: number
}
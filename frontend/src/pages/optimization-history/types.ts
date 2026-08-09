export interface OptimizationHistory {
  id: number
  optimizationId: string
  dateGenerated: string
  duration: number
  totalProfit: number
  totalProductionCost: number
  productsProduced: number
}

export interface ProfitTrend {
  optimizationId: string
  profit: number
}
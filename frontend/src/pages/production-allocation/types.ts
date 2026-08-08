export interface ProductionPlan {
  id: number
  productName: string
  quantity: number
}

export interface OptimizationSummary {
  totalRevenue: number
  totalCost: number
  totalProfit: number

  startTime: string
  endTime: string
  duration: string
}
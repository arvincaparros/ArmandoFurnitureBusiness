export interface ForecastItem {
  id: number
  furnitureProduct: string
  historicalSales: number
  predictedDemand: number
  forecastPeriod: string
  confidenceLevel: number
  status: 'success' | 'pending' | 'failed'
}

export interface ForecastChartData {
  month: string
  historicalDemand?: number
  forecastedDemand?: number
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  message: string
}
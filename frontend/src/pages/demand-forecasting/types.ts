// Matches the real backend domain (app/services/forecasting.py::
// determine_forecast_status) rather than an invented success/pending/
// failed enum - see the Demand Forecasting Phase D report for why.
// READY = forecast exists with sufficient confidence, LOW_CONFIDENCE =
// forecast exists but confidence is limited, NO_DATA = insufficient
// qualifying history to forecast from at all.
export type ForecastStatus = 'NO_DATA' | 'LOW_CONFIDENCE' | 'READY'

export interface ForecastItem {
  id: number
  furnitureProduct: string
  historicalSales: number
  predictedDemand: number
  forecastPeriod: string
  confidenceLevel: number
  status: ForecastStatus
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
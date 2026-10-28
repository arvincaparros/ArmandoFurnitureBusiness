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
  // X-axis label for one graph point: the transaction date for a
  // historical record, the first day of the forecasted month for the
  // forecast point. Several transactions can share a date, so this
  // label is NOT guaranteed to be unique - each row is still its own
  // point.
  date: string
  // Records which side of the historical/forecast boundary this row
  // belongs to, so the tooltip never presents a forecast as a sale.
  isForecast: boolean
  // Tooltip-only context for a historical row.
  transactionNumber?: string
  quantityProduced?: number
  // Exactly one of these is set per row. The chart additionally reuses
  // the last historical row's value as the forecast line's start, so
  // the dashed segment connects to the real history.
  historicalDemand?: number
  forecastedDemand?: number
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  message: string
}
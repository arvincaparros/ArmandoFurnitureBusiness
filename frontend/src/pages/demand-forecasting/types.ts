import type { ForecastPointType } from './api/forecastTypes'

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
  // Short x-axis label for one graph point: the transaction date for a
  // historical record, the first day of the forecasted month for the
  // forecast point - e.g. "Aug 23". The year is left to `fullDate` so
  // a dense axis of one label per transaction stays legible. Several
  // transactions can share a date, so this label is NOT guaranteed to
  // be unique - each row is still its own point.
  date: string
  // Full date for the tooltip - e.g. "Aug 23, 2026". Never rounded to
  // a month boundary: it is the exact day the API returned.
  fullDate: string
  // Records which side of the historical/forecast boundary this row
  // belongs to, so the tooltip never presents a forecast as a sale.
  isForecast: boolean
  // Which kind of event this row is - see forecastTypes.ts. The
  // tooltip branches on this rather than on which value is
  // defined. No per-event identity (transaction/application ids)
  // survives weekly aggregation, so none is carried here.
  pointType: ForecastPointType
  // The PLOTTED production value, set only on a PRODUCTION row.
  // Its source is the production application ledger. A week can
  // represent more than one applied batch, so this is a total, not
  // a single application's quantity.
  producedQuantity?: number
  // Exactly one of historicalDemand/forecastedDemand is set per row
  // (producedQuantity is independent of both, since a PRODUCTION row
  // is its own pointType). The chart additionally reuses the last
  // historical row's value as the forecast line's start, so the
  // dashed segment connects to the real history.
  historicalDemand?: number
  forecastedDemand?: number
}

// One row of the Forecast Table: the original one-row-per-product
// shape (furniture product, historical sales, predicted demand,
// forecast period, confidence level - no status). Built from GET
// /api/forecast/timeseries requested for every product at once (see
// forecastAdapter.ts::toUiForecastTableItems), with historicalSales
// = that product's latest historical week and predictedDemand = its
// first forecast week, so every product gets exactly one row and
// neither value is ever blank.
export interface ForecastTableItem {
  id: number
  furnitureProduct: string
  historicalSales: number
  predictedDemand: number
  forecastPeriod: string
  confidenceLevel: number
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  message: string
}
// Mirrors backend/app/schemas/forecast.py's ProductForecast/
// ForecastResponse exactly - these are the Phase E wire-contract field
// names (historical_sales/predicted_demand/confidence_level/
// forecast_status), not the internal historical_quantity/
// forecast_quantity keys the service layer uses before serialization.
// All Decimal fields arrive as JSON strings, never bare numbers, same
// convention as every other module in this backend.

export interface ForecastProductResponse {
  product_id: number
  product_name: string
  historical_sales: string
  predicted_demand: string
  trend: string
  confidence_level: string
  forecast_status: string
}

// forecast_period is a constant string ("NEXT_CYCLE" today) describing
// which cycle the forecast is for, not a calendar date - see
// forecastAdapter.ts for how it's presented in the UI.
export interface ForecastResponse {
  forecast_period: string
  products: ForecastProductResponse[]
}

// point_type is the authoritative kind discriminator (see
// backend/app/schemas/forecast.py):
//   SALE       - one calendar week's sold total (zero-filled).
//                historical_sales is the quantity SOLD.
//                quantity_produced is always null here.
//   PRODUCTION - one calendar week's produced total (ledger-sourced,
//                plus the pre-rollout legacy fallback). Never
//                zero-filled - a week with no production has no
//                PRODUCTION point. quantity_produced is the quantity
//                PRODUCED.
//   FORECAST   - one of the three trailing weekly projections.
// is_forecast stays available and is true exactly when point_type is
// 'FORECAST'. Per-event identity (transaction/application ids) does
// not survive weekly aggregation and is not part of this shape.
export type ForecastPointType = 'SALE' | 'PRODUCTION' | 'FORECAST'

export interface ForecastTimeSeriesPoint {
  period: string
  point_type: ForecastPointType
  historical_sales: string | null
  quantity_produced: string | null
  predicted_demand: string | null
  is_forecast: boolean
}

export interface ProductTimeSeriesResponse {
  product_id: number
  product_name: string
  // Computed once from the product's weekly sold series and shared
  // by every forecast point in `series` - never per-point.
  trend: string
  confidence_level: string
  series: ForecastTimeSeriesPoint[]
}

export interface ForecastTimeSeriesResponse {
  products: ProductTimeSeriesResponse[]
}

// Mirrors backend/app/schemas/forecast.py's ForecastChatRequest/
// ForecastChatResponse - POST /api/forecast/chat. The backend builds
// its own forecast-data context server-side (see app/services/
// forecast_chat.py::build_forecast_context) and never recomputes the
// forecast algorithm - only the user's raw message is sent up.
export interface ForecastChatRequest {
  message: string
}

export interface ForecastChatResponse {
  reply: string
}

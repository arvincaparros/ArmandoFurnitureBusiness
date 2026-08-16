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

// Mirrors backend/app/schemas/forecast.py's ForecastTimeSeriesPoint/
// ProductTimeSeries/ForecastTimeSeriesResponse exactly. is_forecast is
// the authoritative historical/forecast boundary marker - per the
// service (app/services/forecasting.py::get_forecast_timeseries), a
// historical point always has historical_sales set and
// predicted_demand null, the single forecast point always has the
// reverse - never assume this from array position.
export interface ForecastTimeSeriesPoint {
  period: string
  historical_sales: string | null
  predicted_demand: string | null
  is_forecast: boolean
}

export interface ProductTimeSeriesResponse {
  product_id: number
  product_name: string
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

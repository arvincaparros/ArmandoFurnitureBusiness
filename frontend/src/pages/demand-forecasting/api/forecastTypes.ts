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
// predicted_demand null, a forecast point always has the reverse -
// never assume this from array position.
//
// A historical point is one calendar WEEK (Monday start) of
// qualifying sales, zero-filled for weeks with none - "period" is
// that week's Monday date (YYYY-MM-DD). Each of the (exactly three)
// trailing forecast points is the week immediately following the
// last, with no transaction behind it. transaction_id/
// transaction_number are never populated under weekly aggregation
// (kept nullable rather than removed, since nothing still relies on
// them). quantity_produced is carried for display only - the plotted
// value is historical_sales (quantity sold), the measure the forecast
// is built from.
export interface ForecastTimeSeriesPoint {
  period: string
  transaction_id: number | null
  transaction_number: string | null
  historical_sales: string | null
  quantity_produced: string | null
  predicted_demand: string | null
  is_forecast: boolean
}

export interface ProductTimeSeriesResponse {
  product_id: number
  product_name: string
  // Computed once from the product's weekly historical series and
  // shared by every forecast point in `series` - never per-point.
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

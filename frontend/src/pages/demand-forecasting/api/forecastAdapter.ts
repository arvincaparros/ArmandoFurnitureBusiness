import type {
  ForecastProductResponse,
  ForecastResponse,
  ForecastTimeSeriesResponse,
} from './forecastTypes'
import type {
  ForecastChartData,
  ForecastItem,
  ForecastStatus,
} from '../types'

// Every backend Decimal field arrives as a JSON string, never a bare
// number - see backend/docs/demand-forecasting-api-contract.md §14
// for the same behavior documented on this exact module.
function parseDecimal(value: string): number {
  const parsed = Number(value)

  return Number.isFinite(parsed) ? parsed : 0
}

// forecast_period is a constant, not a calendar date - approved
// product decision: display "NEXT_CYCLE" as "Next Cycle" and do not
// derive or fabricate an actual month/date anywhere on the frontend.
const FORECAST_PERIOD_LABELS: Record<string, string> = {
  NEXT_CYCLE: 'Next Cycle',
}

function toDisplayPeriod(period: string): string {
  return FORECAST_PERIOD_LABELS[period] ?? period
}

const KNOWN_STATUSES: readonly ForecastStatus[] = [
  'NO_DATA',
  'LOW_CONFIDENCE',
  'READY',
]

function toForecastStatus(status: string): ForecastStatus {
  return (KNOWN_STATUSES as readonly string[]).includes(status)
    ? (status as ForecastStatus)
    : 'NO_DATA'
}

function toUiForecastItem(
  product: ForecastProductResponse,
  forecastPeriod: string,
): ForecastItem {
  return {
    id: product.product_id,
    furnitureProduct: product.product_name,
    historicalSales: parseDecimal(product.historical_sales),
    predictedDemand: parseDecimal(product.predicted_demand),
    forecastPeriod: toDisplayPeriod(forecastPeriod),
    confidenceLevel: parseDecimal(product.confidence_level),
    status: toForecastStatus(product.forecast_status),
  }
}

export function toUiForecastItems(
  forecast: ForecastResponse | undefined,
): ForecastItem[] {
  if (!forecast) {
    return []
  }

  return forecast.products.map((product) =>
    toUiForecastItem(product, forecast.forecast_period),
  )
}

// --- Chart product selector -------------------------------------------
//
// Reuses the already-fetched GET /api/forecast product list (product_id
// + product_name) rather than making a separate /api/products request -
// the forecast table and the chart's product selector share this one
// source of active products.

export interface ForecastProductOption {
  value: string
  label: string
}

export function toForecastProductOptions(
  forecast: ForecastResponse | undefined,
): ForecastProductOption[] {
  if (!forecast) {
    return []
  }

  return forecast.products.map((product) => ({
    value: String(product.product_id),
    label: product.product_name,
  }))
}

// --- Chart data ----------------------------------------------------------

function parseNullableDecimal(
  value: string | null,
): number | undefined {
  if (value === null) {
    return undefined
  }

  return parseDecimal(value)
}

// period is "YYYY-MM" (e.g. "2026-09") - presented the same way the
// existing chart's mock data was styled ("Sep '26"), purely a display
// format, no date fabrication.
function formatPeriodLabel(period: string): string {
  const [year, month] = period.split('-').map(Number)

  if (!year || !month) {
    return period
  }

  const label = new Date(year, month - 1, 1).toLocaleString(
    'en-US',
    { month: 'short' },
  )

  return `${label} '${String(year).slice(2)}`
}

// is_forecast is the backend's authoritative historical/forecast
// boundary marker (see forecastTypes.ts) - branched on directly rather
// than inferred from which value happens to be non-null. No point
// duplication or interpolation: a point contributes to exactly one of
// historicalDemand/forecastedDemand, matching the real API response.
export function toUiForecastChartData(
  timeseries: ForecastTimeSeriesResponse | undefined,
): ForecastChartData[] {
  const series = timeseries?.products[0]?.series

  if (!series) {
    return []
  }

  return series.map((point) => ({
    month: formatPeriodLabel(point.period),
    historicalDemand: point.is_forecast
      ? undefined
      : parseNullableDecimal(point.historical_sales),
    forecastedDemand: point.is_forecast
      ? parseNullableDecimal(point.predicted_demand)
      : undefined,
  }))
}

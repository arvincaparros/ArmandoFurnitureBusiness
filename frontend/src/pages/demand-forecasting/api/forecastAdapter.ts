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

// period is "YYYY-MM-DD": the transaction date for a historical
// point, the first day of the forecasted month for the forecast
// point. Presented the way the chart's mock data was styled
// ("Aug 23 '26"), purely a display format - the date is never
// shifted, rounded or spread to improve spacing.
function formatDateLabel(period: string): string {
  const [year, month, day] = period.split('-').map(Number)

  if (!year || !month) {
    return period
  }

  const label = new Date(year, month - 1, day || 1).toLocaleString(
    'en-US',
    { month: 'short' },
  )

  const shortYear = `'${String(year).slice(2)}`

  // Zero-padded day, matching the chart's design reference
  // ("Sep 01 '26").
  return day
    ? `${label} ${String(day).padStart(2, '0')} ${shortYear}`
    : `${label} ${shortYear}`
}

// is_forecast is the backend's authoritative historical/forecast
// boundary marker (see forecastTypes.ts) - branched on directly rather
// than inferred from which value happens to be non-null.
//
// One row per API point, in API order: every qualifying transaction
// keeps its own row (two sales on the same date stay two points) and
// the series ends with the backend's single forecast point. Nothing is
// grouped, deduplicated or sliced here.
export function toUiForecastChartData(
  timeseries: ForecastTimeSeriesResponse | undefined,
): ForecastChartData[] {
  const series = timeseries?.products[0]?.series

  if (!series) {
    return []
  }

  return series.map((point) => ({
    date: formatDateLabel(point.period),
    isForecast: point.is_forecast,
    transactionNumber: point.transaction_number ?? undefined,
    quantityProduced: parseNullableDecimal(point.quantity_produced),
    historicalDemand: point.is_forecast
      ? undefined
      : parseNullableDecimal(point.historical_sales),
    forecastedDemand: point.is_forecast
      ? parseNullableDecimal(point.predicted_demand)
      : undefined,
  }))
}

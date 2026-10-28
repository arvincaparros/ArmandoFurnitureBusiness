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
// point. Both labels below are display-only - the date is never
// shifted, rounded or spread to improve spacing, so a point always
// sits on the day the API reported.
interface PeriodParts {
  year: number
  month: string
  day?: number
}

function parsePeriod(period: string): PeriodParts | null {
  const [year, month, day] = period.split('-').map(Number)

  if (!year || !month) {
    return null
  }

  return {
    year,
    month: new Date(year, month - 1, day || 1).toLocaleString('en-US', {
      month: 'short',
    }),
    day: day || undefined,
  }
}

// Axis label: month and zero-padded day only ("Aug 23", "Sep 06").
// The year is deliberately omitted to keep one label per transaction
// readable; the tooltip shows the full date instead. The chart labels
// the forecast point the same way, from its own API period ("Nov 01").
function formatAxisLabel(period: string): string {
  const parts = parsePeriod(period)

  if (!parts) {
    return period
  }

  return parts.day
    ? `${parts.month} ${String(parts.day).padStart(2, '0')}`
    : parts.month
}

// Tooltip label: the full date, including the year ("Aug 23, 2026").
function formatFullDate(period: string): string {
  const parts = parsePeriod(period)

  if (!parts) {
    return period
  }

  return parts.day
    ? `${parts.month} ${String(parts.day).padStart(2, '0')}, ${parts.year}`
    : `${parts.month} ${parts.year}`
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
    date: formatAxisLabel(point.period),
    fullDate: formatFullDate(point.period),
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

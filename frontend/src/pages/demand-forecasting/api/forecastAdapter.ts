import type {
  ForecastProductResponse,
  ForecastResponse,
  ForecastTimeSeriesPoint,
  ForecastTimeSeriesResponse,
} from './forecastTypes'
import type {
  ForecastChartData,
  ForecastItem,
  ForecastStatus,
  ForecastTableItem,
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

// End of the week starting on `weekStartIso` ("YYYY-MM-DD", a Monday)
// - always 6 days later, matching the backend's Monday-start weekly
// boundary exactly, never recomputed differently anywhere else.
function weekEndIso(weekStartIso: string): string {
  const [year, month, day] = weekStartIso.split('-').map(Number)
  const end = new Date(year, month - 1, day + 6)

  return [
    end.getFullYear(),
    String(end.getMonth() + 1).padStart(2, '0'),
    String(end.getDate()).padStart(2, '0'),
  ].join('-')
}

// Table-only week-range label, e.g. "Nov 2 - Nov 8" - reuses the same
// period parsing the chart's axis/tooltip labels already go through.
function formatWeekRangeLabel(weekStartIso: string): string {
  const start = parsePeriod(weekStartIso)
  const end = parsePeriod(weekEndIso(weekStartIso))

  if (!start || !end) {
    return weekStartIso
  }

  return `${start.month} ${start.day} - ${end.month} ${end.day}`
}

// One row per PRODUCT (the original table shape), built from GET
// /api/forecast/timeseries requested with no product_id - the same
// endpoint and request the backend already supports for "every
// active product's series at once". historicalSales is that
// product's latest historical week; predictedDemand is its first
// forecast week (week 1, immediately after the latest historical
// week) - both come from the one already-fetched weekly series, so
// neither is ever blank and nothing is recomputed independently of
// the chart's own data (see toUiForecastChartData below, which reads
// the same per-product series for whichever product is selected).
export function toUiForecastTableItems(
  timeseries: ForecastTimeSeriesResponse | undefined,
): ForecastTableItem[] {
  if (!timeseries) {
    return []
  }

  return timeseries.products.map((product) => {
    // Filtered to SALE specifically, not merely "not a forecast
    // point" - a PRODUCTION point is also non-forecast, and picking
    // it here would read historical_sales as null and silently
    // report 0 sold for a product that was recently produced but
    // hasn't sold yet this week.
    const salePoints = product.series.filter(
      (point) => point.point_type === 'SALE',
    )
    const forecastPoints = product.series.filter(
      (point) => point.is_forecast,
    )

    const latestSale = salePoints.at(-1)
    const firstForecast = forecastPoints[0]

    return {
      id: product.product_id,
      furnitureProduct: product.product_name,
      historicalSales: latestSale
        ? parseDecimal(latestSale.historical_sales ?? '0')
        : 0,
      predictedDemand: firstForecast
        ? Math.ceil(
            parseDecimal(firstForecast.predicted_demand ?? '0'),
          )
        : 0,
      forecastPeriod: firstForecast
        ? formatWeekRangeLabel(firstForecast.period)
        : '—',
      confidenceLevel: parseDecimal(product.confidence_level),
    }
  })
}

// is_forecast is the backend's authoritative historical/forecast
// boundary marker (see forecastTypes.ts) - branched on directly rather
// than inferred from which value happens to be non-null. point_type
// further distinguishes a SALE week from a PRODUCTION week, since
// both are non-forecast.
//
// One row per weekly point, in API order: every historical week keeps
// its own row and the series ends with the backend's three forecast
// weeks. Nothing is grouped, deduplicated or sliced here. The caller
// (see useForecast.ts) picks which product's series to pass in.
export function toUiForecastChartData(
  series: ForecastTimeSeriesPoint[],
): ForecastChartData[] {
  return series.map((point) => ({
    date: formatAxisLabel(point.period),
    fullDate: formatFullDate(point.period),
    pointType: point.point_type,
    isForecast: point.is_forecast,
    historicalDemand: point.point_type === 'SALE'
      ? parseNullableDecimal(point.historical_sales)
      : undefined,
    producedQuantity: point.point_type === 'PRODUCTION'
      ? parseNullableDecimal(point.quantity_produced)
      : undefined,
    forecastedDemand: point.is_forecast
      ? parseNullableDecimal(point.predicted_demand)
      : undefined,
  }))
}

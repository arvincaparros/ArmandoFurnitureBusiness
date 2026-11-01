import { describe, expect, it } from 'vitest'

import {
  toUiForecastChartData,
  toUiForecastWeekRows,
} from './forecastAdapter'

import type {
  ForecastTimeSeriesPoint,
  ForecastTimeSeriesResponse,
} from './forecastTypes'

// 2026-01-05 is a Monday, used as the weekly anchor throughout so
// boundaries are easy to verify by eye.
//
// 3 historical weeks (one zero-filled gap), then exactly 3 forecast
// weeks: quantities [10, 0, 20] -> avg_delta = (20-10)/2 = 5 ->
// 25, 30, 35.
const HISTORICAL_WEEKS: readonly [
  period: string,
  sold: string,
  produced: string,
][] = [
  ['2026-01-05', '10.0000', '10.0000'],
  ['2026-01-12', '0.0000', '0.0000'],
  ['2026-01-19', '20.0000', '22.0000'],
]

function toHistoricalPoint(
  [period, sold, produced]: readonly [string, string, string],
): ForecastTimeSeriesPoint {
  return {
    period,
    transaction_id: null,
    transaction_number: null,
    historical_sales: sold,
    quantity_produced: produced,
    predicted_demand: null,
    is_forecast: false,
  }
}

const FORECAST_WEEKS: readonly ForecastTimeSeriesPoint[] = [
  {
    period: '2026-01-26',
    transaction_id: null,
    transaction_number: null,
    historical_sales: null,
    quantity_produced: null,
    predicted_demand: '25.0000',
    is_forecast: true,
  },
  {
    period: '2026-02-02',
    transaction_id: null,
    transaction_number: null,
    historical_sales: null,
    quantity_produced: null,
    predicted_demand: '30.0000',
    is_forecast: true,
  },
  {
    period: '2026-02-09',
    transaction_id: null,
    transaction_number: null,
    historical_sales: null,
    quantity_produced: null,
    predicted_demand: '35.0000',
    is_forecast: true,
  },
]

const chairTimeseries: ForecastTimeSeriesResponse = {
  products: [
    {
      product_id: 7,
      product_name: 'Chair',
      trend: 'INCREASING',
      confidence_level: '66.67',
      series: [
        ...HISTORICAL_WEEKS.map(toHistoricalPoint),
        ...FORECAST_WEEKS,
      ],
    },
  ],
}

describe('toUiForecastChartData', () => {
  it('turns 3 historical weeks and 3 forecast weeks into 6 points', () => {
    const data = toUiForecastChartData(chairTimeseries)

    expect(data).toHaveLength(6)

    expect(data.map((point) => point.date)).toEqual([
      'Jan 05',
      'Jan 12',
      'Jan 19',
      'Jan 26',
      'Feb 02',
      'Feb 09',
    ])

    expect(data.map((point) => point.historicalDemand)).toEqual([
      10, 0, 20, undefined, undefined, undefined,
    ])

    expect(
      data.filter((point) => point.historicalDemand !== undefined),
    ).toHaveLength(3)
    expect(data.filter((point) => point.isForecast)).toHaveLength(3)
  })

  it('accounts for every unit and never counts a forecast week as a sale', () => {
    const data = toUiForecastChartData(chairTimeseries)

    const soldUnits = data.reduce(
      (total, point) => total + (point.historicalDemand ?? 0),
      0,
    )
    const producedUnits = data.reduce(
      (total, point) => total + (point.quantityProduced ?? 0),
      0,
    )

    expect(soldUnits).toBe(30)
    expect(producedUnits).toBe(32)

    const forecastPoints = data.filter(
      (point) => point.forecastedDemand !== undefined,
    )

    expect(forecastPoints).toHaveLength(3)
    expect(forecastPoints.map((point) => point.forecastedDemand)).toEqual([
      25, 30, 35,
    ])
    expect(
      forecastPoints.every(
        (point) => point.historicalDemand === undefined,
      ),
    ).toBe(true)
  })

  it('formats the axis day exactly as the API sent it', () => {
    expect(
      toUiForecastChartData(chairTimeseries).every(
        (point) => !point.date.includes('20'),
      ),
    ).toBe(true)
  })

  it('returns no points when the product has no series yet', () => {
    expect(toUiForecastChartData(undefined)).toEqual([])
  })
})

describe('toUiForecastWeekRows', () => {
  it('labels each historical week with its Monday-start range, in the Historical Sales column only', () => {
    const rows = toUiForecastWeekRows(chairTimeseries)

    const historicalRows = rows.filter(
      (row) => row.historicalSales !== undefined,
    )

    expect(historicalRows).toHaveLength(3)
    expect(historicalRows.map((row) => row.weekLabel)).toEqual([
      'Jan 5 - Jan 11',
      'Jan 12 - Jan 18',
      'Jan 19 - Jan 25',
    ])
    expect(historicalRows.map((row) => row.historicalSales)).toEqual([
      10, 0, 20,
    ])
    // Historical Sales and Predicted Demand never share a row -
    // Predicted Demand/Confidence Level stay unset on these rows.
    expect(
      historicalRows.every(
        (row) =>
          row.predictedDemand === undefined &&
          row.confidenceLevel === undefined,
      ),
    ).toBe(true)
  })

  it('puts every forecast week in the Predicted Demand column with the shared product-level confidence', () => {
    const rows = toUiForecastWeekRows(chairTimeseries)

    const forecastRows = rows.filter(
      (row) => row.predictedDemand !== undefined,
    )

    expect(forecastRows).toHaveLength(3)
    expect(forecastRows.map((row) => row.predictedDemand)).toEqual([
      25, 30, 35,
    ])
    expect(
      forecastRows.every((row) => row.historicalSales === undefined),
    ).toBe(true)
    expect(
      forecastRows.every((row) => row.confidenceLevel === 66.67),
    ).toBe(true)
  })

  it('carries the furniture product name on every row', () => {
    const rows = toUiForecastWeekRows(chairTimeseries)

    expect(rows.every((row) => row.furnitureProduct === 'Chair')).toBe(
      true,
    )
  })

  it('returns no rows when the product has no series yet', () => {
    expect(toUiForecastWeekRows(undefined)).toEqual([])
  })
})

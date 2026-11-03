import { describe, expect, it } from 'vitest'

import {
  toUiForecastChartData,
  toUiForecastTableItems,
} from './forecastAdapter'

import type {
  ForecastTimeSeriesPoint,
  ForecastTimeSeriesResponse,
  ProductTimeSeriesResponse,
} from './forecastTypes'

// 2026-01-05 is a Monday, used as the weekly anchor throughout so
// boundaries are easy to verify by eye.
//
// 3 historical sale weeks (one zero-filled gap), two of which also
// have their own PRODUCTION point (a week with zero production gets
// no PRODUCTION point at all - see forecastTypes.ts), then exactly 3
// forecast weeks: sold quantities [10, 0, 20] -> avg_delta =
// (20-10)/2 = 5 -> 25, 30, 35.
const HISTORICAL_WEEKS: readonly [
  period: string,
  sold: string,
  produced: string,
][] = [
  ['2026-01-05', '10.0000', '10.0000'],
  ['2026-01-12', '0.0000', '0.0000'],
  ['2026-01-19', '20.0000', '22.0000'],
]

function toSalePoint(
  [period, sold]: readonly [string, string, string],
): ForecastTimeSeriesPoint {
  return {
    period,
    point_type: 'SALE',
    historical_sales: sold,
    quantity_produced: null,
    predicted_demand: null,
    is_forecast: false,
  }
}

function toProductionPoint(
  [period, , produced]: readonly [string, string, string],
): ForecastTimeSeriesPoint {
  return {
    period,
    point_type: 'PRODUCTION',
    historical_sales: null,
    quantity_produced: produced,
    predicted_demand: null,
    is_forecast: false,
  }
}

const FORECAST_WEEKS: readonly ForecastTimeSeriesPoint[] = [
  {
    period: '2026-01-26',
    point_type: 'FORECAST',
    historical_sales: null,
    quantity_produced: null,
    predicted_demand: '25.0000',
    is_forecast: true,
  },
  {
    period: '2026-02-02',
    point_type: 'FORECAST',
    historical_sales: null,
    quantity_produced: null,
    predicted_demand: '30.0000',
    is_forecast: true,
  },
  {
    period: '2026-02-09',
    point_type: 'FORECAST',
    historical_sales: null,
    quantity_produced: null,
    predicted_demand: '35.0000',
    is_forecast: true,
  },
]

// Only the two non-zero-production weeks (Jan 05, Jan 19) get a
// PRODUCTION point, matching the "never zero-filled" rule for
// production documented on ForecastTimeSeriesPoint.
const CHAIR_SERIES: ForecastTimeSeriesPoint[] = [
  ...HISTORICAL_WEEKS.flatMap((week) => {
    const [, , produced] = week
    const points: ForecastTimeSeriesPoint[] = []

    if (produced !== '0.0000') {
      points.push(toProductionPoint(week))
    }

    points.push(toSalePoint(week))

    return points
  }),
  ...FORECAST_WEEKS,
]

const chairTimeseries: ForecastTimeSeriesResponse = {
  products: [
    {
      product_id: 7,
      product_name: 'Chair',
      trend: 'INCREASING',
      confidence_level: '66.67',
      series: CHAIR_SERIES,
    },
  ],
}

describe('toUiForecastChartData', () => {
  it('turns historical sale/production weeks and forecast weeks into one point per row', () => {
    const data = toUiForecastChartData(CHAIR_SERIES)

    // 2 production points (Jan 05, Jan 19) + 3 sale points + 3
    // forecast points = 8 rows. No row is dropped or merged.
    expect(data).toHaveLength(8)

    expect(data.map((point) => point.date)).toEqual([
      'Jan 05',
      'Jan 05',
      'Jan 12',
      'Jan 19',
      'Jan 19',
      'Jan 26',
      'Feb 02',
      'Feb 09',
    ])

    expect(data.map((point) => point.pointType)).toEqual([
      'PRODUCTION',
      'SALE',
      'SALE',
      'PRODUCTION',
      'SALE',
      'FORECAST',
      'FORECAST',
      'FORECAST',
    ])

    expect(data.map((point) => point.historicalDemand)).toEqual([
      undefined,
      10,
      0,
      undefined,
      20,
      undefined,
      undefined,
      undefined,
    ])

    expect(
      data.filter((point) => point.historicalDemand !== undefined),
    ).toHaveLength(3)
    expect(data.filter((point) => point.isForecast)).toHaveLength(3)
  })

  it('accounts for every unit and never counts a forecast week as a sale', () => {
    const data = toUiForecastChartData(CHAIR_SERIES)

    const soldUnits = data.reduce(
      (total, point) => total + (point.historicalDemand ?? 0),
      0,
    )
    const producedUnits = data.reduce(
      (total, point) => total + (point.producedQuantity ?? 0),
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
      toUiForecastChartData(CHAIR_SERIES).every(
        (point) => !point.date.includes('20'),
      ),
    ).toBe(true)
  })

  it('returns no points for an empty series', () => {
    expect(toUiForecastChartData([])).toEqual([])
  })
})

describe('toUiForecastChartData production points', () => {
  it('plots produced units from PRODUCTION points only, never on a SALE row', () => {
    const rows = toUiForecastChartData([
      {
        period: '2026-10-26',
        point_type: 'PRODUCTION',
        historical_sales: null,
        quantity_produced: '6.0000',
        predicted_demand: null,
        is_forecast: false,
      },
      {
        period: '2026-10-28',
        point_type: 'SALE',
        historical_sales: '2.0000',
        quantity_produced: null,
        predicted_demand: null,
        is_forecast: false,
      },
    ])

    expect(rows[0].pointType).toBe('PRODUCTION')
    expect(rows[0].producedQuantity).toBe(6)
    expect(rows[0].historicalDemand).toBeUndefined()
    expect(rows[0].forecastedDemand).toBeUndefined()

    expect(rows[1].pointType).toBe('SALE')
    expect(rows[1].producedQuantity).toBeUndefined()
    expect(rows[1].historicalDemand).toBe(2)
  })
})

// A second product with zero history: all 3 series points are
// forecast, no historical points at all - exercises the "no
// historical week" fallback.
const diningTableTimeseries: ProductTimeSeriesResponse = {
  product_id: 9,
  product_name: 'Dining Table',
  trend: 'NO_DATA',
  confidence_level: '0.00',
  series: [
    {
      period: '2026-11-02',
      point_type: 'FORECAST',
      historical_sales: null,
      quantity_produced: null,
      predicted_demand: '0',
      is_forecast: true,
    },
    {
      period: '2026-11-09',
      point_type: 'FORECAST',
      historical_sales: null,
      quantity_produced: null,
      predicted_demand: '0',
      is_forecast: true,
    },
    {
      period: '2026-11-16',
      point_type: 'FORECAST',
      historical_sales: null,
      quantity_produced: null,
      predicted_demand: '0',
      is_forecast: true,
    },
  ],
}

const allProductsTimeseries: ForecastTimeSeriesResponse = {
  products: [chairTimeseries.products[0], diningTableTimeseries],
}

describe('toUiForecastTableItems', () => {
  it('returns exactly one row per product, for every product in the response', () => {
    const items = toUiForecastTableItems(allProductsTimeseries)

    expect(items).toHaveLength(2)
    expect(items.map((item) => item.furnitureProduct)).toEqual([
      'Chair',
      'Dining Table',
    ])
  })

  it('fills Historical Sales from the latest historical week and Predicted Demand from the first forecast week, on the same row', () => {
    const items = toUiForecastTableItems(allProductsTimeseries)
    const chair = items[0]

    // Latest SALE week is 2026-01-19 (quantity 20), first forecast
    // week is 2026-01-26 (predicted 25) - both on one row, neither
    // blank, and the interleaved PRODUCTION point for the same week
    // does not shift which SALE point counts as "latest".
    expect(chair.historicalSales).toBe(20)
    expect(chair.predictedDemand).toBe(25)
    expect(chair.forecastPeriod).toBe('Jan 26 - Feb 1')
    expect(chair.confidenceLevel).toBe(66.67)
  })

  it('falls back to 0 for Historical Sales when a product has no historical weeks at all', () => {
    const items = toUiForecastTableItems(allProductsTimeseries)
    const diningTable = items[1]

    expect(diningTable.historicalSales).toBe(0)
    expect(diningTable.predictedDemand).toBe(0)
    expect(diningTable.forecastPeriod).toBe('Nov 2 - Nov 8')
    expect(diningTable.confidenceLevel).toBe(0)
  })

  it('returns no rows when there is no timeseries response yet', () => {
    expect(toUiForecastTableItems(undefined)).toEqual([])
  })

  it('rounds a fractional Predicted Demand up to a whole unit', () => {
    const fractional: ForecastTimeSeriesResponse = {
      products: [
        {
          product_id: 11,
          product_name: 'Bed Frame',
          trend: 'STABLE',
          confidence_level: '50.00',
          series: [
            {
              period: '2026-01-26',
              point_type: 'FORECAST',
              historical_sales: null,
              quantity_produced: null,
              predicted_demand: '3.857142857142857',
              is_forecast: true,
            },
          ],
        },
      ],
    }

    const items = toUiForecastTableItems(fractional)

    // Furniture is produced in whole units - ceil, not round/floor,
    // so the table never under-plans production against the
    // forecast.
    expect(items[0].predictedDemand).toBe(4)
  })

  // This is the regression test for the bug this integration fixes:
  // toUiForecastTableItems must read the latest SALE point for
  // Historical Sales, even when a later, non-forecast PRODUCTION
  // point exists further along in the same series.
  it('uses the latest SALE point for historicalSales even when a later PRODUCTION point exists', () => {
    const timeseries: ForecastTimeSeriesResponse = {
      products: [
        {
          product_id: 1,
          product_name: 'Ordinary Chair',
          trend: 'STABLE',
          confidence_level: '80.00',
          series: [
            {
              period: '2026-01-05',
              point_type: 'SALE',
              historical_sales: '10',
              quantity_produced: null,
              predicted_demand: null,
              is_forecast: false,
            },
            {
              period: '2026-01-12',
              point_type: 'PRODUCTION',
              historical_sales: null,
              quantity_produced: '5',
              predicted_demand: null,
              is_forecast: false,
            },
            {
              period: '2026-01-19',
              point_type: 'FORECAST',
              historical_sales: null,
              quantity_produced: null,
              predicted_demand: '12',
              is_forecast: true,
            },
          ],
        },
      ],
    }

    const items = toUiForecastTableItems(timeseries)

    expect(items[0].historicalSales).toBe(10)
  })
})

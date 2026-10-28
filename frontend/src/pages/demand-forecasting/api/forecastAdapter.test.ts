import { describe, expect, it } from 'vitest'

import { toUiForecastChartData } from './forecastAdapter'

import type {
  ForecastTimeSeriesPoint,
  ForecastTimeSeriesResponse,
} from './forecastTypes'

// The adviser's case, row for row from transaction-history (2).csv:
// 9 qualifying sales of "Door ( 60x210 )", each with its own
// transaction number, date, quantity sold and quantity produced, plus
// the single forecast point GET /api/forecast/timeseries appends.
//
// Quantity sold is the plotted value (35 units in total); quantity
// produced (39 units) only travels in the tooltip.
// id, transaction number, date, quantity sold, quantity produced.
type CsvRow = readonly [
  id: string,
  number: string,
  period: string,
  sold: string,
  produced: string,
]

const DOOR_TRANSACTIONS: readonly CsvRow[] = [
  ['101', 'TRX-000140', '2026-08-23', '1.0000', '5.0000'],
  ['102', 'TRX-000153', '2026-08-27', '4.0000', '4.0000'],
  ['103', 'TRX-000158', '2026-08-30', '3.0000', '3.0000'],
  ['104', 'TRX-000169', '2026-09-06', '5.0000', '5.0000'],
  ['105', 'TRX-000186', '2026-09-16', '5.0000', '5.0000'],
  ['106', 'TRX-000191', '2026-09-20', '5.0000', '5.0000'],
  ['107', 'TRX-000203', '2026-09-28', '3.0000', '3.0000'],
  ['108', 'TRX-000215', '2026-10-06', '4.0000', '4.0000'],
  ['109', 'TRX-000226', '2026-10-14', '5.0000', '5.0000'],
]

const FORECAST_POINT: ForecastTimeSeriesPoint = {
  period: '2026-11-01',
  transaction_id: null,
  transaction_number: null,
  historical_sales: null,
  quantity_produced: null,
  // Monthly sold totals [8, 18, 9] -> avg_delta 0.5 -> 9.5.
  predicted_demand: '9.5000',
  is_forecast: true,
}

function toSeriesPoint(
  [id, number, period, sold, produced]: CsvRow,
): ForecastTimeSeriesPoint {
  return {
    period,
    transaction_id: Number(id),
    transaction_number: number,
    historical_sales: sold,
    quantity_produced: produced,
    predicted_demand: null,
    is_forecast: false,
  }
}

const nineTransactionTimeseries: ForecastTimeSeriesResponse = {
  products: [
    {
      product_id: 7,
      product_name: 'Door (60x210)',
      series: [
        ...DOOR_TRANSACTIONS.map(toSeriesPoint),
        FORECAST_POINT,
      ],
    },
  ],
}

describe('toUiForecastChartData', () => {
  it('turns 9 transactions into 9 historical points plus 1 forecast point', () => {
    const data = toUiForecastChartData(nineTransactionTimeseries)

    expect(data).toHaveLength(10)

    // Every transaction keeps its own date on the x-axis, in
    // chronological order, and nothing is grouped by month.
    expect(data.map((point) => point.date)).toEqual([
      "Aug 23 '26",
      "Aug 27 '26",
      "Aug 30 '26",
      "Sep 06 '26",
      "Sep 16 '26",
      "Sep 20 '26",
      "Sep 28 '26",
      "Oct 06 '26",
      "Oct 14 '26",
      "Nov 01 '26",
    ])

    expect(data.map((point) => point.historicalDemand)).toEqual([
      1, 4, 3, 5, 5, 5, 3, 4, 5, undefined,
    ])

    expect(data.filter((point) => point.historicalDemand !== undefined))
      .toHaveLength(9)
    expect(data.filter((point) => point.isForecast)).toHaveLength(1)
  })

  it('accounts for every unit and never counts the forecast as a sale', () => {
    const data = toUiForecastChartData(nineTransactionTimeseries)

    const soldUnits = data.reduce(
      (total, point) => total + (point.historicalDemand ?? 0),
      0,
    )
    const producedUnits = data.reduce(
      (total, point) => total + (point.quantityProduced ?? 0),
      0,
    )

    // No recorded row disappears on the way to the chart.
    expect(soldUnits).toBe(35)
    expect(producedUnits).toBe(39)

    // Exactly one point belongs to the forecast series, and it is the
    // trailing point, not one of the sales.
    const forecastPoints = data.filter(
      (point) => point.forecastedDemand !== undefined,
    )

    expect(forecastPoints).toHaveLength(1)
    expect(forecastPoints[0]).toBe(data[data.length - 1])
    expect(forecastPoints[0].date).toBe("Nov 01 '26")
    expect(forecastPoints[0].forecastedDemand).toBe(9.5)
    expect(forecastPoints[0].historicalDemand).toBeUndefined()
  })

  it('keeps transaction identity so points can be told apart', () => {
    const data = toUiForecastChartData(nineTransactionTimeseries)

    expect(
      data
        .filter((point) => !point.isForecast)
        .map((point) => point.transactionNumber),
    ).toEqual(DOOR_TRANSACTIONS.map(([, number]) => number))

    // The forecast row has no transaction behind it.
    expect(data[data.length - 1].transactionNumber).toBeUndefined()
  })

  it('keeps two transactions on the same date as two separate points', () => {
    const sameDate = toUiForecastChartData({
      products: [
        {
          product_id: 7,
          product_name: 'Door (60x210)',
          series: [
            toSeriesPoint([
              '101',
              'TRX-000140',
              '2026-08-23',
              '1.0000',
              '5.0000',
            ]),
            toSeriesPoint([
              '102',
              'TRX-000153',
              '2026-08-23',
              '4.0000',
              '4.0000',
            ]),
            FORECAST_POINT,
          ],
        },
      ],
    })

    expect(sameDate).toHaveLength(3)
    expect(sameDate.map((point) => point.date)).toEqual([
      "Aug 23 '26",
      "Aug 23 '26",
      "Nov 01 '26",
    ])
    expect(sameDate.map((point) => point.historicalDemand)).toEqual([
      1,
      4,
      undefined,
    ])
    expect(sameDate[0].transactionNumber).not.toBe(
      sameDate[1].transactionNumber,
    )
  })

  it('returns no points when the product has no series yet', () => {
    expect(toUiForecastChartData(undefined)).toEqual([])
  })
})

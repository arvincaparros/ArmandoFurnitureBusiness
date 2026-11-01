import type { ReactNode } from 'react'

import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import useForecast from './useForecast'

import {
  fetchForecast,
  fetchForecastTimeseries,
} from '../api/forecastApi'

import type {
  ForecastResponse,
  ForecastTimeSeriesPoint,
  ForecastTimeSeriesResponse,
} from '../api/forecastTypes'

vi.mock('../api/forecastApi', () => ({
  fetchForecast: vi.fn(),
  fetchForecastTimeseries: vi.fn(),
  generateForecast: vi.fn(),
  sendForecastChatMessage: vi.fn(),
}))

const DOOR_ID = 7
const CHAIR_ID = 8

const forecastResponse: ForecastResponse = {
  forecast_period: 'NEXT_CYCLE',
  products: [
    {
      product_id: DOOR_ID,
      product_name: 'Door (60x210)',
      historical_sales: '9.0000',
      predicted_demand: '9.5000',
      trend: 'INCREASING',
      confidence_level: '50.00',
      forecast_status: 'LOW_CONFIDENCE',
    },
    {
      product_id: CHAIR_ID,
      product_name: 'Chair',
      historical_sales: '9.0000',
      predicted_demand: '9.0000',
      trend: 'STABLE',
      confidence_level: '50.00',
      forecast_status: 'LOW_CONFIDENCE',
    },
  ],
}

const salePoint = (
  period: string,
  sold: string,
  produced: string,
  number: string,
): ForecastTimeSeriesPoint => ({
  period,
  transaction_id: Number(number.replace(/\D/g, '')),
  transaction_number: number,
  historical_sales: sold,
  quantity_produced: produced,
  predicted_demand: null,
  is_forecast: false,
})

const forecastPoint = (
  period: string,
  predicted: string,
): ForecastTimeSeriesPoint => ({
  period,
  transaction_id: null,
  transaction_number: null,
  historical_sales: null,
  quantity_produced: null,
  predicted_demand: predicted,
  is_forecast: true,
})

// The 9 exported "Door ( 60x210 )" sales, one point each, plus the
// single forecast point - see forecastAdapter.test.ts for the same
// fixture.
const DOOR_SALES = [
  salePoint('2026-08-23', '1.0000', '5.0000', 'TRX-000140'),
  salePoint('2026-08-27', '4.0000', '4.0000', 'TRX-000153'),
  salePoint('2026-08-30', '3.0000', '3.0000', 'TRX-000158'),
  salePoint('2026-09-06', '5.0000', '5.0000', 'TRX-000169'),
  salePoint('2026-09-16', '5.0000', '5.0000', 'TRX-000186'),
  salePoint('2026-09-20', '5.0000', '5.0000', 'TRX-000191'),
  salePoint('2026-09-28', '3.0000', '3.0000', 'TRX-000203'),
  salePoint('2026-10-06', '4.0000', '4.0000', 'TRX-000215'),
  salePoint('2026-10-14', '5.0000', '5.0000', 'TRX-000226'),
]

// Both products' series, as returned by the unfiltered
// GET /api/forecast/timeseries (no product_id) - the hook now fetches
// every active product's series in one request and derives both the
// table (all products) and the chart (the selected one) from it.
const allTimeseries: ForecastTimeSeriesResponse = {
  products: [
    {
      product_id: DOOR_ID,
      product_name: 'Door (60x210)',
      trend: 'INCREASING',
      confidence_level: '50.00',
      series: [...DOOR_SALES, forecastPoint('2026-11-01', '9.5000')],
    },
    {
      product_id: CHAIR_ID,
      product_name: 'Chair',
      trend: 'STABLE',
      confidence_level: '50.00',
      series: [
        salePoint('2026-05-04', '9.0000', '9.0000', 'TRX-CH-1'),
        forecastPoint('2026-06-01', '9.0000'),
      ],
    },
  ],
}

beforeEach(() => {
  vi.mocked(fetchForecast).mockReset()
  vi.mocked(fetchForecastTimeseries).mockReset()

  vi.mocked(fetchForecast).mockResolvedValue(forecastResponse)
  vi.mocked(fetchForecastTimeseries).mockResolvedValue(allTimeseries)
})

const renderForecast = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  })

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )

  return renderHook(() => useForecast(), { wrapper })
}

describe('useForecast product selection', () => {
  it('fetches every product\'s series in one unfiltered request', async () => {
    renderForecast()

    await waitFor(() => {
      expect(fetchForecastTimeseries).toHaveBeenCalled()
    })

    expect(fetchForecastTimeseries).toHaveBeenCalledTimes(1)
    expect(fetchForecastTimeseries).toHaveBeenCalledWith()
  })

  it('opens the chart on the first product with history and plots every transaction', async () => {
    const { result } = renderForecast()

    await waitFor(() => {
      expect(result.current.chartData).toHaveLength(10)
    })

    expect(result.current.selectedProductId).toBe(DOOR_ID)

    // 9 historical points (one per transaction) then exactly one
    // forecast point.
    expect(
      result.current.chartData.filter(
        (point) => point.historicalDemand !== undefined,
      ),
    ).toHaveLength(9)
    expect(
      result.current.chartData.filter(
        (point) => point.forecastedDemand !== undefined,
      ),
    ).toHaveLength(1)

    expect(result.current.chartData[0].date).toBe('Aug 23')
    expect(result.current.chartData[9].date).toBe('Nov 01')
  })

  it('swaps the chart to the newly selected product without a second fetch', async () => {
    const { result } = renderForecast()

    await waitFor(() => {
      expect(result.current.chartData).toHaveLength(10)
    })

    act(() => {
      result.current.setSelectedProductId(CHAIR_ID)
    })

    await waitFor(() => {
      expect(result.current.chartData).toHaveLength(2)
    })

    expect(result.current.selectedProductId).toBe(CHAIR_ID)

    // Picked out of the already-fetched response - no re-fetch on
    // product switch.
    expect(fetchForecastTimeseries).toHaveBeenCalledTimes(1)

    // The previous product's transactions are nowhere in the new
    // series: one of its own sales, then its own forecast point.
    expect(result.current.chartData).toEqual([
      {
        date: 'May 04',
        fullDate: 'May 04, 2026',
        isForecast: false,
        transactionNumber: 'TRX-CH-1',
        quantityProduced: 9,
        historicalDemand: 9,
        forecastedDemand: undefined,
      },
      {
        date: 'Jun 01',
        fullDate: 'Jun 01, 2026',
        isForecast: true,
        transactionNumber: undefined,
        quantityProduced: undefined,
        historicalDemand: undefined,
        forecastedDemand: 9,
      },
    ])
  })
})

describe('useForecast table rows', () => {
  it('returns one row per product, for every product, regardless of which one is selected', async () => {
    const { result } = renderForecast()

    await waitFor(() => {
      expect(result.current.forecastTableItems).toHaveLength(2)
    })

    expect(
      result.current.forecastTableItems.map(
        (item) => item.furnitureProduct,
      ),
    ).toEqual(['Door (60x210)', 'Chair'])

    act(() => {
      result.current.setSelectedProductId(CHAIR_ID)
    })

    // Selecting a different product for the chart does not change
    // which products appear in the table.
    expect(result.current.forecastTableItems).toHaveLength(2)
  })

  it('fills historical sales and predicted demand on the same row for each product', async () => {
    const { result } = renderForecast()

    await waitFor(() => {
      expect(result.current.forecastTableItems).toHaveLength(2)
    })

    const door = result.current.forecastTableItems[0]

    // Door's latest historical week (2026-10-14) and first forecast
    // week (2026-11-01).
    expect(door.historicalSales).toBe(5)
    expect(door.predictedDemand).toBe(9.5)
  })
})

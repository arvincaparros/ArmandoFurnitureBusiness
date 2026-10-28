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

const doorTimeseries: ForecastTimeSeriesResponse = {
  products: [
    {
      product_id: DOOR_ID,
      product_name: 'Door (60x210)',
      series: [
        ...DOOR_SALES,
        forecastPoint('2026-11-01', '9.5000'),
      ],
    },
  ],
}

const chairTimeseries: ForecastTimeSeriesResponse = {
  products: [
    {
      product_id: CHAIR_ID,
      product_name: 'Chair',
      series: [
        salePoint('2026-05-04', '9.0000', '9.0000', 'TRX-CH-1'),
        forecastPoint('2026-06-01', '9.0000'),
      ],
    },
  ],
}

let resolveChairRequest:
  | ((value: ForecastTimeSeriesResponse) => void)
  | null = null

beforeEach(() => {
  resolveChairRequest = null

  vi.mocked(fetchForecast).mockReset()
  vi.mocked(fetchForecastTimeseries).mockReset()

  vi.mocked(fetchForecast).mockResolvedValue(forecastResponse)

  vi.mocked(fetchForecastTimeseries).mockImplementation(
    (productId: number) => {
      if (productId === CHAIR_ID) {
        // Held open so the test can observe the in-flight state.
        return new Promise<ForecastTimeSeriesResponse>((resolve) => {
          resolveChairRequest = resolve
        })
      }

      return Promise.resolve(doorTimeseries)
    },
  )
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
  it('opens on the first product with history and plots every transaction', async () => {
    const { result } = renderForecast()

    await waitFor(() => {
      expect(result.current.chartData).toHaveLength(10)
    })

    expect(result.current.selectedProductId).toBe(DOOR_ID)
    expect(fetchForecastTimeseries).toHaveBeenCalledWith(DOOR_ID)

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

    expect(result.current.chartData[0].date).toBe("Aug 23 '26")
    expect(result.current.chartData[9].date).toBe("Nov 01 '26")
  })

  it('swaps to the newly selected product without showing the old one', async () => {
    const { result } = renderForecast()

    await waitFor(() => {
      expect(result.current.chartData).toHaveLength(10)
    })

    act(() => {
      result.current.setSelectedProductId(CHAIR_ID)
    })

    expect(result.current.selectedProductId).toBe(CHAIR_ID)

    // In flight: the previous product's points are gone rather than
    // lingering until the new response lands.
    expect(result.current.chartData).toEqual([])

    await act(async () => {
      if (!resolveChairRequest) {
        throw new Error('the chair series was never requested')
      }

      resolveChairRequest(chairTimeseries)
    })

    await waitFor(() => {
      expect(result.current.chartData).toHaveLength(2)
    })

    expect(fetchForecastTimeseries).toHaveBeenCalledWith(CHAIR_ID)

    // The previous product's transactions are nowhere in the new
    // series: one of its own sales, then its own forecast point.
    expect(result.current.chartData).toEqual([
      {
        date: "May 04 '26",
        isForecast: false,
        transactionNumber: 'TRX-CH-1',
        quantityProduced: 9,
        historicalDemand: 9,
        forecastedDemand: undefined,
      },
      {
        date: "Jun 01 '26",
        isForecast: true,
        transactionNumber: undefined,
        quantityProduced: undefined,
        historicalDemand: undefined,
        forecastedDemand: 9,
      },
    ])
  })
})

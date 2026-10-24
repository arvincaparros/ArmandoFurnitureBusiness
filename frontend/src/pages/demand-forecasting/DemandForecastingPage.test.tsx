import { render, screen, waitFor } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import DemandForecastingPage from './DemandForecastingPage'
import { ThemeProvider } from '../../theme/ThemeContext'
import {
  fetchForecast,
  fetchForecastTimeseries,
} from './api/forecastApi'

import type {
  ForecastResponse,
  ForecastTimeSeriesResponse,
} from './api/forecastTypes'

vi.mock('./api/forecastApi', () => ({
  fetchForecast: vi.fn(),
  fetchForecastTimeseries: vi.fn(),
  generateForecast: vi.fn(),
  sendForecastChatMessage: vi.fn(),
}))

// Real GET /api/forecast output for a product with no recorded sales:
// 200, every value zero, forecast_status NO_DATA (see
// backend/docs/demand-forecasting-api-contract.md §7). This is the
// state that follows applying a plan, because applying only saves
// production allocations - it never records sales.
const noHistoryForecast: ForecastResponse = {
  forecast_period: 'NEXT_CYCLE',
  products: [
    {
      product_id: 1,
      product_name: 'Test Dining Table',
      historical_sales: '0.0000',
      predicted_demand: '0.0000',
      trend: 'NO_DATA',
      confidence_level: '0.00',
      forecast_status: 'NO_DATA',
    },
  ],
}

// ...and the matching timeseries: a single zero-unit forecast point,
// no historical point.
const noHistoryTimeseries: ForecastTimeSeriesResponse = {
  products: [
    {
      product_id: 1,
      product_name: 'Test Dining Table',
      series: [
        {
          period: '2026-11',
          historical_sales: null,
          predicted_demand: '0.0000',
          is_forecast: true,
        },
      ],
    },
  ],
}

const withHistoryForecast: ForecastResponse = {
  forecast_period: 'NEXT_CYCLE',
  products: [
    {
      product_id: 2,
      product_name: 'Test Chair',
      historical_sales: '8.0000',
      predicted_demand: '8.0000',
      trend: 'STABLE',
      confidence_level: '8.33',
      forecast_status: 'LOW_CONFIDENCE',
    },
  ],
}

const withHistoryTimeseries: ForecastTimeSeriesResponse = {
  products: [
    {
      product_id: 2,
      product_name: 'Test Chair',
      series: [
        {
          period: '2026-09',
          historical_sales: '8.0000',
          predicted_demand: null,
          is_forecast: false,
        },
        {
          period: '2026-10',
          historical_sales: null,
          predicted_demand: '8.0000',
          is_forecast: true,
        },
      ],
    },
  ],
}

beforeEach(() => {
  vi.mocked(fetchForecast).mockReset()
  vi.mocked(fetchForecastTimeseries).mockReset()
})

const renderPage = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        // Deterministic, fast error states - the default retry (3
        // attempts with backoff) would otherwise keep the page in
        // isLoading past waitFor's default timeout.
        retry: false,
      },
    },
  })

  return render(
    <MantineProvider>
      <Notifications />
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <DemandForecastingPage />
          </MemoryRouter>
        </QueryClientProvider>
      </ThemeProvider>
    </MantineProvider>,
  )
}

describe('DemandForecastingPage no-sales-history state', () => {
  it('explains the sales-history workflow when every product is NO_DATA', async () => {
    vi.mocked(fetchForecast).mockResolvedValue(noHistoryForecast)
    vi.mocked(fetchForecastTimeseries).mockResolvedValue(
      noHistoryTimeseries,
    )

    renderPage()

    await waitFor(() => {
      expect(
        screen.getByText('No sales history yet'),
      ).toBeInTheDocument()
    })

    // Actionable: links to where sales are actually recorded.
    expect(
      screen.getByRole('link', { name: /transaction history/i }),
    ).toHaveAttribute('href', '/history')

    // Chart does not draw a lone zero dot with no history to plot.
    await waitFor(() => {
      expect(
        screen.getByText(/no sales history for this product yet/i),
      ).toBeInTheDocument()
    })

    // The NO_DATA rows are still normal data, not an error state.
    expect(screen.getByText('0.0%')).toBeInTheDocument()
    expect(screen.queryByText(/unable to load forecast/i)).toBeNull()
  })

  it('hides the guidance once sales history exists', async () => {
    vi.mocked(fetchForecast).mockResolvedValue(withHistoryForecast)
    vi.mocked(fetchForecastTimeseries).mockResolvedValue(
      withHistoryTimeseries,
    )

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('8.3%')).toBeInTheDocument()
    })

    expect(
      screen.queryByText('No sales history yet'),
    ).toBeNull()
    expect(
      screen.queryByText(/no sales history for this product yet/i),
    ).toBeNull()
  })

  it('shows the API error state without the sales-history guidance', async () => {
    vi.mocked(fetchForecast).mockRejectedValue(
      new Error('network error'),
    )

    renderPage()

    await waitFor(() => {
      expect(
        screen.getByText('Unable to load forecast.'),
      ).toBeInTheDocument()
    })

    expect(
      screen.queryByText('No sales history yet'),
    ).toBeNull()
  })
})

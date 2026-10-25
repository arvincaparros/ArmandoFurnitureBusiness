import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

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

// jsdom's viewport is 1024px wide, so half of it is 512px.
const setViewportWidth = (width: number) => {
  Object.defineProperty(window, 'innerWidth', {
    configurable: true,
    writable: true,
    value: width,
  })
}

describe('DemandForecastingPage resizable AI Assistant', () => {
  const openAssistant = async () => {
    const user = userEvent.setup()

    // The desktop launcher and the mobile toggle share one label; the
    // first one is the desktop panel this feature resizes.
    await user.click(
      screen.getAllByRole('button', {
        name: 'Open AI Assistant',
      })[0],
    )

    return user
  }

  const getHandle = () =>
    screen.getByRole('separator', { name: 'Resize AI Assistant' })

  beforeEach(() => {
    vi.mocked(fetchForecast).mockResolvedValue(noHistoryForecast)
    vi.mocked(fetchForecastTimeseries).mockResolvedValue(
      noHistoryTimeseries,
    )
  })

  afterEach(() => {
    setViewportWidth(1024)
  })

  it('renders a resize handle bounded by the panel minimum and half the viewport', async () => {
    renderPage()

    await openAssistant()

    const handle = getHandle()

    expect(handle).toHaveAttribute('aria-valuenow', '360')
    expect(handle).toHaveAttribute('aria-valuemin', '360')
    expect(handle).toHaveAttribute('aria-valuemax', '512')
  })

  it('follows a left drag, clamps at both limits, and stops tracking on mouse up', async () => {
    renderPage()

    const user = await openAssistant()

    fireEvent.mouseDown(getHandle(), { clientX: 700 })
    fireEvent.mouseMove(window, { clientX: 200 })

    // 360 + (700 - 200) = 860 -> clamped to 1024 / 2.
    expect(getHandle()).toHaveAttribute('aria-valuenow', '512')
    expect(
      document
        .querySelector<HTMLElement>('[style*="--chat-width"]')
        ?.style.getPropertyValue('--chat-width'),
    ).toBe('512px')

    // Dragging back to the right returns it to the original width.
    fireEvent.mouseMove(window, { clientX: 900 })

    expect(getHandle()).toHaveAttribute('aria-valuenow', '360')

    fireEvent.mouseUp(window)

    // No mousemove listener survives the drag.
    fireEvent.mouseMove(window, { clientX: 0 })

    expect(getHandle()).toHaveAttribute('aria-valuenow', '360')

    // The resized panel is still a working chat panel.
    expect(
      screen.getAllByPlaceholderText(
        'Ask about demand forecasts...',
      ).length,
    ).toBeGreaterThan(0)

    await user.click(
      screen.getAllByRole('button', {
        name: 'Close AI Assistant',
      })[0],
    )

    expect(
      screen.queryByRole('separator', {
        name: 'Resize AI Assistant',
      }),
    ).not.toBeInTheDocument()
  })

  it('clamps the panel back inside half the viewport when the window shrinks', async () => {
    renderPage()

    await openAssistant()

    fireEvent.mouseDown(getHandle(), { clientX: 700 })
    fireEvent.mouseMove(window, { clientX: 200 })
    fireEvent.mouseUp(window)

    expect(getHandle()).toHaveAttribute('aria-valuenow', '512')

    setViewportWidth(800)
    fireEvent(window, new Event('resize'))

    expect(getHandle()).toHaveAttribute('aria-valuenow', '400')
    expect(getHandle()).toHaveAttribute('aria-valuemax', '400')
  })
})

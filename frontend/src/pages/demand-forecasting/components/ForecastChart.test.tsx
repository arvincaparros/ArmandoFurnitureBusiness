import type { ReactNode } from 'react'

import { render, screen } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'
import { describe, expect, it, vi } from 'vitest'

import ForecastChart from './ForecastChart'

import type { ForecastChartData } from '../types'

// ResponsiveContainer has no layout in jsdom, so the rendered chart
// produces no DOM to assert on. The Mantine wrapper is replaced by a
// probe that captures the props the chart hands to recharts instead -
// that is where the x-axis key, the tick formatter and the tooltip
// renderer are decided.
interface CapturedXAxisProps {
  interval?: unknown
  minTickGap?: number
  tickFormatter?: (value: unknown) => string
}

interface CapturedTooltipProps {
  payload?: readonly { payload?: ForecastChartData }[]
}

interface CapturedChartProps {
  data: (ForecastChartData & { axisKey: string })[]
  dataKey: string
  series: {
    name: string
    label?: string
    strokeDasharray?: string | number
  }[]
  xAxisProps?: CapturedXAxisProps
  tooltipProps?: {
    content?: (props: CapturedTooltipProps) => ReactNode
  }
}

const { captured } = vi.hoisted(() => ({
  captured: { current: null as CapturedChartProps | null },
}))

vi.mock('@mantine/charts', () => ({
  LineChart: (props: CapturedChartProps) => {
    captured.current = props

    return <div data-testid="line-chart" />
  },
}))

// 2026-01-05 is a Monday: a PRODUCTION point and 3 historical SALE
// weeks (one zero-filled gap), followed by exactly the 3 forecast
// weeks GET /api/forecast/timeseries always returns - the same
// fixture shape as forecastAdapter.test.ts.
const sale = (
  date: string,
  fullDate: string,
  sold: number,
): ForecastChartData => ({
  date,
  fullDate,
  pointType: 'SALE',
  isForecast: false,
  historicalDemand: sold,
})

const produced = (
  date: string,
  fullDate: string,
  quantity: number,
): ForecastChartData => ({
  date,
  fullDate,
  pointType: 'PRODUCTION',
  isForecast: false,
  producedQuantity: quantity,
})

const forecastWeek = (
  date: string,
  fullDate: string,
  predicted: number,
): ForecastChartData => ({
  date,
  fullDate,
  pointType: 'FORECAST',
  isForecast: true,
  forecastedDemand: predicted,
})

const WEEKLY_ROWS: ForecastChartData[] = [
  produced('Jan 05', 'Jan 05, 2026', 12),
  sale('Jan 05', 'Jan 05, 2026', 10),
  sale('Jan 12', 'Jan 12, 2026', 0),
  sale('Jan 19', 'Jan 19, 2026', 20),
  forecastWeek('Jan 26', 'Jan 26, 2026', 25),
  forecastWeek('Feb 02', 'Feb 02, 2026', 30),
  forecastWeek('Feb 09', 'Feb 09, 2026', 35),
]

// A single forecast-only row, reused by the production-series tests
// below for a product with no history at all.
const forecastRow = forecastWeek('Nov 01', 'Nov 01, 2026', 0)

const renderChart = (data: ForecastChartData[]): CapturedChartProps => {
  captured.current = null

  render(
    <MantineProvider>
      <ForecastChart
        data={data}
        isLoading={false}
        isError={false}
        hasProducts
      />
    </MantineProvider>,
  )

  // Re-read through a widened type: the reset above narrows the
  // property to null inside this scope, while the probe fills it in
  // during render.
  const chart = captured.current as CapturedChartProps | null

  if (!chart) {
    throw new Error('the chart was never rendered')
  }

  return chart
}

const renderTooltip = (row: ForecastChartData) => {
  const content = captured.current?.tooltipProps?.content

  if (!content) {
    throw new Error('the chart has no tooltip renderer')
  }

  render(
    <MantineProvider>
      {content({ payload: [{ payload: row }] })}
    </MantineProvider>,
  )
}

describe('ForecastChart x-axis', () => {
  it('plots every row and keeps each one on its own x slot', () => {
    const chart = renderChart(WEEKLY_ROWS)

    expect(screen.getByTestId('line-chart')).toBeInTheDocument()

    // 1 production week + 3 historical sale weeks + 3 forecast
    // weeks: no row is dropped.
    expect(chart.data).toHaveLength(7)
    expect(chart.dataKey).toBe('axisKey')

    const axisKeys = chart.data.map((row) => row.axisKey)

    expect(new Set(axisKeys).size).toBe(7)
  })

  it('labels each slot with the short month-and-day date', () => {
    const chart = renderChart(WEEKLY_ROWS)
    const formatTick = chart.xAxisProps?.tickFormatter

    expect(formatTick).toBeTypeOf('function')

    const labels = chart.data.map((row) => formatTick?.(row.axisKey))

    expect(labels).toEqual([
      'Jan 05',
      'Jan 05',
      'Jan 12',
      'Jan 19',
      'Jan 26',
      'Feb 02',
      'Feb 09',
    ])
  })

  it('thins dense labels without removing points', () => {
    const chart = renderChart(WEEKLY_ROWS)

    // First and last ticks always survive, so the final forecast week
    // stays labelled however many weeks are plotted.
    expect(chart.xAxisProps?.interval).toBe('preserveStartEnd')
    expect(chart.xAxisProps?.minTickGap).toBe(12)
  })
})

describe('ForecastChart tooltip', () => {
  it('shows the full week date and the quantity sold, never a production line on a sale row', () => {
    renderChart(WEEKLY_ROWS)
    renderTooltip(WEEKLY_ROWS[1])

    expect(screen.getByText('Jan 05, 2026')).toBeInTheDocument()
    expect(
      screen.getByText('Quantity sold: 10 units'),
    ).toBeInTheDocument()
    expect(screen.queryByText(/Applied production/)).toBeNull()
  })

  it('shows only the date for a production week - no Applied Production line', () => {
    renderChart(WEEKLY_ROWS)
    renderTooltip(WEEKLY_ROWS[0])

    expect(screen.getByText('Jan 05, 2026')).toBeInTheDocument()
    expect(screen.queryByText(/Applied production/)).toBeNull()
    expect(screen.queryByText(/Quantity sold/)).toBeNull()
    expect(screen.queryByText(/Forecasted demand/)).toBeNull()
  })

  it('labels a forecast week as forecast, using its own API date', () => {
    renderChart(WEEKLY_ROWS)
    renderTooltip(WEEKLY_ROWS[4])

    expect(screen.getByText('Jan 26, 2026')).toBeInTheDocument()
    expect(
      screen.getByText('Forecasted demand: 25 units'),
    ).toBeInTheDocument()
    expect(screen.queryByText(/Quantity sold/)).toBeNull()
  })
})

describe('ForecastChart series', () => {
  it('keeps the forecast dashed, separately labelled, and connects to the last historical week', () => {
    const chart = renderChart(WEEKLY_ROWS)

    expect(chart.series).toEqual([
      {
        name: 'historicalDemand',
        label: 'Historical Demand (Weekly)',
      },
      // The Applied Production series was removed from the graph
      // (and its legend entry with it) - only Historical Demand and
      // Forecasted Demand are plotted now.
      {
        name: 'forecastedDemand',
        label: 'Forecasted Demand',
        color: 'grape.6',
        strokeDasharray: '6 6',
      },
    ])

    // The dashed segment starts on the last historical week (index 3,
    // "Jan 19" - index 0 is the production-only week), which still
    // reports its own weekly total.
    expect(chart.data[3].isForecast).toBe(false)
    expect(chart.data[3].forecastedDemand).toBe(
      chart.data[3].historicalDemand,
    )

    // All three forecast weeks follow it.
    expect(chart.data.slice(4).every((row) => row.isForecast)).toBe(
      true,
    )
    expect(
      chart.data.slice(4).map((row) => row.forecastedDemand),
    ).toEqual([25, 30, 35])
  })
})

describe('ForecastChart production series', () => {
  const productionRow: ForecastChartData = {
    date: 'Oct 26',
    fullDate: 'Oct 26, 2026',
    pointType: 'PRODUCTION',
    isForecast: false,
    producedQuantity: 6,
  }

  it('renders the chart when a product has production but no sales', () => {
    const chart = renderChart([productionRow, forecastRow])

    expect(
      screen.queryByText(/No sales or production recorded/),
    ).not.toBeInTheDocument()

    // The chart still renders (production alone is plottable data,
    // not an empty product) but no longer has its own Applied
    // Production series/legend entry - only Historical Demand and
    // Forecasted Demand are ever plotted now.
    expect(
      chart.series.map((entry) => entry.label),
    ).not.toContain('Applied Production')

    expect(
      chart.series.map((entry) => entry.name),
    ).not.toContain('producedQuantity')
  })

  it('still explains an entirely empty product', () => {
    // Only a forecast point: nothing plottable, so the component
    // returns the message instead of a chart.
    render(
      <MantineProvider>
        <ForecastChart
          data={[forecastRow]}
          isLoading={false}
          isError={false}
          hasProducts
        />
      </MantineProvider>,
    )

    expect(
      screen.getByText(/No sales or production recorded/),
    ).toBeInTheDocument()
  })

  it('no longer shows an applied production figure in the tooltip', () => {
    renderChart([productionRow, forecastRow])
    renderTooltip(productionRow)

    expect(
      screen.queryByText(/Applied production/),
    ).toBeNull()
  })
})

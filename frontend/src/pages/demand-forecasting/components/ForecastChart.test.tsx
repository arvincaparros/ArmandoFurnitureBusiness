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

// 2026-01-05 is a Monday: 3 historical weeks (one zero-filled gap)
// followed by exactly the 3 forecast weeks GET /api/forecast/
// timeseries always returns - the same fixture shape as
// forecastAdapter.test.ts.
const sale = (
  date: string,
  fullDate: string,
  sold: number,
): ForecastChartData => ({
  date,
  fullDate,
  isForecast: false,
  quantityProduced: sold,
  historicalDemand: sold,
})

const forecastWeek = (
  date: string,
  fullDate: string,
  predicted: number,
): ForecastChartData => ({
  date,
  fullDate,
  isForecast: true,
  forecastedDemand: predicted,
})

const WEEKLY_ROWS: ForecastChartData[] = [
  sale('Jan 05', 'Jan 05, 2026', 10),
  sale('Jan 12', 'Jan 12, 2026', 0),
  sale('Jan 19', 'Jan 19, 2026', 20),
  forecastWeek('Jan 26', 'Jan 26, 2026', 25),
  forecastWeek('Feb 02', 'Feb 02, 2026', 30),
  forecastWeek('Feb 09', 'Feb 09, 2026', 35),
]

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

    // 3 historical weeks + 3 forecast weeks: no row is dropped.
    expect(chart.data).toHaveLength(6)
    expect(chart.dataKey).toBe('axisKey')

    const axisKeys = chart.data.map((row) => row.axisKey)

    expect(new Set(axisKeys).size).toBe(6)
  })

  it('labels each slot with the short month-and-day date', () => {
    const chart = renderChart(WEEKLY_ROWS)
    const formatTick = chart.xAxisProps?.tickFormatter

    expect(formatTick).toBeTypeOf('function')

    const labels = chart.data.map((row) => formatTick?.(row.axisKey))

    expect(labels).toEqual([
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
  it('shows the full week date and the quantity sold', () => {
    renderChart(WEEKLY_ROWS)
    renderTooltip(WEEKLY_ROWS[0])

    expect(screen.getByText('Jan 05, 2026')).toBeInTheDocument()
    expect(
      screen.getByText('Quantity sold: 10 units'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Quantity produced: 10 units'),
    ).toBeInTheDocument()
  })

  it('labels a forecast week as forecast, using its own API date', () => {
    renderChart(WEEKLY_ROWS)
    renderTooltip(WEEKLY_ROWS[3])

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
      {
        name: 'forecastedDemand',
        label: 'Forecasted Demand',
        color: 'grape.6',
        strokeDasharray: '6 6',
      },
    ])

    // The dashed segment starts on the last historical week (index 2,
    // "Jan 19"), which still reports its own weekly total.
    expect(chart.data[2].isForecast).toBe(false)
    expect(chart.data[2].forecastedDemand).toBe(
      chart.data[2].historicalDemand,
    )

    // All three forecast weeks follow it.
    expect(chart.data.slice(3).every((row) => row.isForecast)).toBe(
      true,
    )
    expect(
      chart.data.slice(3).map((row) => row.forecastedDemand),
    ).toEqual([25, 30, 35])
  })
})

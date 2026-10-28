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

// The adviser's 9 "Door ( 60x210 )" sales, in API order, plus the one
// forecast point - the same fixture as forecastAdapter.test.ts.
const sale = (
  date: string,
  fullDate: string,
  sold: number,
  transactionNumber: string,
): ForecastChartData => ({
  date,
  fullDate,
  isForecast: false,
  transactionNumber,
  quantityProduced: sold,
  historicalDemand: sold,
})

const forecastRow: ForecastChartData = {
  date: 'Nov 01',
  fullDate: 'Nov 01, 2026',
  isForecast: true,
  forecastedDemand: 9.5,
}

const DOOR_ROWS: ForecastChartData[] = [
  sale('Aug 23', 'Aug 23, 2026', 1, 'TRX-000140'),
  sale('Aug 27', 'Aug 27, 2026', 4, 'TRX-000153'),
  sale('Aug 30', 'Aug 30, 2026', 3, 'TRX-000158'),
  sale('Sep 06', 'Sep 06, 2026', 5, 'TRX-000169'),
  sale('Sep 16', 'Sep 16, 2026', 5, 'TRX-000186'),
  sale('Sep 20', 'Sep 20, 2026', 5, 'TRX-000191'),
  sale('Sep 28', 'Sep 28, 2026', 3, 'TRX-000203'),
  sale('Oct 06', 'Oct 06, 2026', 4, 'TRX-000215'),
  sale('Oct 14', 'Oct 14, 2026', 5, 'TRX-000226'),
  forecastRow,
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
    const chart = renderChart(DOOR_ROWS)

    expect(screen.getByTestId('line-chart')).toBeInTheDocument()

    // 9 transactions + 1 forecast: no row is dropped for the axis.
    expect(chart.data).toHaveLength(10)
    expect(chart.dataKey).toBe('axisKey')

    const axisKeys = chart.data.map((row) => row.axisKey)

    expect(new Set(axisKeys).size).toBe(10)
  })

  it('labels each slot with the short month-and-day date', () => {
    const chart = renderChart(DOOR_ROWS)
    const formatTick = chart.xAxisProps?.tickFormatter

    expect(formatTick).toBeTypeOf('function')

    const labels = chart.data.map((row) =>
      formatTick?.(row.axisKey),
    )

    expect(labels).toEqual([
      'Aug 23',
      'Aug 27',
      'Aug 30',
      'Sep 06',
      'Sep 16',
      'Sep 20',
      'Sep 28',
      'Oct 06',
      'Oct 14',
      'Nov 01',
    ])
  })

  it('thins dense labels without removing points', () => {
    const chart = renderChart(DOOR_ROWS)

    // First and last ticks always survive, so the forecast date stays
    // labelled however many transactions are plotted.
    expect(chart.xAxisProps?.interval).toBe('preserveStartEnd')
    expect(chart.xAxisProps?.minTickGap).toBe(12)
  })

  it('keeps two transactions on the same date as two points', () => {
    const chart = renderChart([
      sale('Aug 23', 'Aug 23, 2026', 1, 'TRX-000140'),
      sale('Aug 23', 'Aug 23, 2026', 4, 'TRX-000153'),
      forecastRow,
    ])

    expect(chart.data).toHaveLength(3)

    const formatTick = chart.xAxisProps?.tickFormatter

    // Same visible label, different x slots - neither point is hidden
    // behind the other, and both keep their own transaction.
    expect(chart.data.map((row) => formatTick?.(row.axisKey))).toEqual([
      'Aug 23',
      'Aug 23',
      'Nov 01',
    ])
    expect(new Set(chart.data.map((row) => row.axisKey)).size).toBe(3)
    expect(chart.data[0].transactionNumber).not.toBe(
      chart.data[1].transactionNumber,
    )
  })
})

describe('ForecastChart tooltip', () => {
  it('shows the full transaction date and the quantity sold', () => {
    renderChart(DOOR_ROWS)
    renderTooltip(DOOR_ROWS[0])

    expect(screen.getByText('Aug 23, 2026')).toBeInTheDocument()
    expect(
      screen.getByText('Quantity sold: 1 units'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Quantity produced: 1 units'),
    ).toBeInTheDocument()
    expect(screen.getByText('TRX-000140')).toBeInTheDocument()
  })

  it('labels the forecast row as forecast, using its API date', () => {
    renderChart(DOOR_ROWS)
    renderTooltip(forecastRow)

    expect(screen.getByText('Nov 01, 2026')).toBeInTheDocument()
    expect(
      screen.getByText('Forecasted demand: 9.5 units'),
    ).toBeInTheDocument()
    expect(screen.queryByText(/Quantity sold/)).toBeNull()
  })
})

describe('ForecastChart series', () => {
  it('keeps the forecast dashed and separately labelled', () => {
    const chart = renderChart(DOOR_ROWS)

    expect(chart.series).toEqual([
      {
        name: 'historicalDemand',
        label: 'Historical Demand (Transaction)',
      },
      {
        name: 'forecastedDemand',
        label: 'Forecasted Demand',
        color: 'grape.6',
        strokeDasharray: '6 6',
      },
    ])

    // The dashed segment starts on the last real transaction, which
    // still reports its own sale in the tooltip.
    expect(chart.data[8].isForecast).toBe(false)
    expect(chart.data[8].forecastedDemand).toBe(
      chart.data[8].historicalDemand,
    )
    expect(chart.data[9].isForecast).toBe(true)
  })
})

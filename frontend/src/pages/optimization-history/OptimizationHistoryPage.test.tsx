import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import OptimizationHistoryPage from './OptimizationHistoryPage'
import { ThemeProvider } from '../../theme/ThemeContext'

import type { OptimizationHistory, ProfitTrend } from './types'
import useOptimizationHistory from './hooks/useOptimizationHistory'

vi.mock('./hooks/useOptimizationHistory', () => ({
  default: vi.fn(),
}))

// Recharts needs measured dimensions jsdom does not provide, so the
// chart is stubbed. It renders exactly what the real chart's X-axis
// shows (dataKey="optimizationId"), which is what the column
// regression test asserts on.
vi.mock('./components/OptimizationHistoryChart', () => ({
  default: ({ data }: { data: ProfitTrend[] }) => (
    <div data-testid="profit-trend-labels">
      {data.map((point) => (
        <span key={point.optimizationId}>{point.optimizationId}</span>
      ))}
    </div>
  ),
}))

// Unique per run, so page slicing stays assertable now that the
// Optimization ID column is not rendered.
const generatedAtFor = (id: number) =>
  `2026-09-${String(id).padStart(2, '0')} 15:45:13`

// Mirrors the newest-first order the hook returns: id N is newest.
const makeHistory = (
  count: number,
  firstId = count,
): OptimizationHistory[] =>
  Array.from({ length: count }, (_, index) => {
    const id = firstId - index

    return {
      id,
      optimizationId: `OP-${id}`,
      dateGenerated: generatedAtFor(id),
      duration: 600,
      totalProfit: 100000,
      totalProductionCost: 130000,
      productsProduced: 30,
    }
  })

const mockHistory = (
  runs: OptimizationHistory[],
  profitTrendData: ProfitTrend[] = [],
) => {
  vi.mocked(useOptimizationHistory).mockReturnValue({
    optimizationHistory: runs,
    profitTrendData,
    isLoading: false,
    isError: false,
  })
}

const pageUi = () => (
  <MantineProvider>
    <ThemeProvider>
      <OptimizationHistoryPage />
    </ThemeProvider>
  </MantineProvider>
)

const renderPage = () => render(pageUi())

beforeEach(() => {
  vi.mocked(useOptimizationHistory).mockReset()
  mockHistory([])
})

describe('OptimizationHistoryPage pagination', () => {
  it('renders the empty state without pagination controls', () => {
    renderPage()

    expect(
      screen.getByText('No optimization history found.'),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Previous' }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Next' }),
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/^Page \d+ of \d+$/)).not.toBeInTheDocument()
  })

  it('shows all 10 runs and no controls when exactly one page exists', () => {
    mockHistory(makeHistory(10))

    renderPage()

    expect(screen.getAllByText(/^2026-\d{2}-\d{2} 15:45:13$/)).toHaveLength(10)
    expect(
      screen.queryByRole('button', { name: 'Previous' }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Next' }),
    ).not.toBeInTheDocument()
  })

  it('slices more than 10 runs into pages with bounded Previous/Next', async () => {
    const user = userEvent.setup()

    mockHistory(makeHistory(25))

    renderPage()

    expect(screen.getByText('Page 1 of 3')).toBeInTheDocument()
    expect(screen.getAllByText(/^2026-\d{2}-\d{2} 15:45:13$/)).toHaveLength(10)
    expect(screen.getByText(generatedAtFor(25))).toBeInTheDocument()
    expect(screen.queryByText(generatedAtFor(15))).not.toBeInTheDocument()

    const previous = screen.getByRole('button', { name: 'Previous' })
    const next = screen.getByRole('button', { name: 'Next' })

    expect(previous).toBeDisabled()
    expect(next).toBeEnabled()

    await user.click(next)

    expect(screen.getByText('Page 2 of 3')).toBeInTheDocument()
    expect(screen.getAllByText(/^2026-\d{2}-\d{2} 15:45:13$/)).toHaveLength(10)
    expect(screen.getByText(generatedAtFor(15))).toBeInTheDocument()
    expect(screen.queryByText(generatedAtFor(25))).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeEnabled()

    await user.click(screen.getByRole('button', { name: 'Next' }))

    expect(screen.getByText('Page 3 of 3')).toBeInTheDocument()
    expect(screen.getAllByText(/^2026-\d{2}-\d{2} 15:45:13$/)).toHaveLength(5)
    expect(screen.getByText(generatedAtFor(5))).toBeInTheDocument()
    expect(screen.getByText(generatedAtFor(1))).toBeInTheDocument()
    expect(screen.queryByText(generatedAtFor(6))).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Previous' }))

    expect(screen.getByText('Page 2 of 3')).toBeInTheDocument()
    expect(screen.getByText(generatedAtFor(15))).toBeInTheDocument()
  })

  it('returns to page 1 when the dataset changes', async () => {
    const user = userEvent.setup()

    mockHistory(makeHistory(25))

    const { rerender } = renderPage()

    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('button', { name: 'Next' }))

    expect(screen.getByText('Page 3 of 3')).toBeInTheDocument()

    // Simulate a refetch after a new run (25 -> 26 records).
    mockHistory(makeHistory(26))

    rerender(pageUi())

    expect(screen.getByText('Page 1 of 3')).toBeInTheDocument()
    expect(screen.getByText(generatedAtFor(26))).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
  })
})

describe('OptimizationHistoryPage columns', () => {
  it('hides the Optimization ID column but keeps the run labels on the chart', () => {
    const runs = makeHistory(8, 171)

    // The adapter reverses the newest-first history for the chart, so
    // the X-axis reads OP-164 (oldest) through OP-171 (newest).
    const trend = [...runs].reverse().map((run) => ({
      optimizationId: run.optimizationId,
      profit: run.totalProfit,
    }))

    mockHistory(runs, trend)

    renderPage()

    expect(
      screen.queryByRole('columnheader', {
        name: 'Optimization ID',
      }),
    ).not.toBeInTheDocument()

    const table = screen.getByRole('table')

    expect(within(table).queryByText(/^OP-\d+$/)).not.toBeInTheDocument()

    const titles = [
      'Date Generated',
      'Duration (s)',
      'Total Profit',
      'Total Production Cost',
      'Products Produced',
    ]

    for (const title of titles) {
      expect(
        screen.getByRole('columnheader', { name: title }),
      ).toBeInTheDocument()
    }

    const labels = within(screen.getByTestId('profit-trend-labels'))

    expect(labels.getAllByText(/^OP-\d+$/)).toHaveLength(8)
    expect(labels.getByText('OP-164')).toBeInTheDocument()
    expect(labels.getByText('OP-171')).toBeInTheDocument()
  })
})

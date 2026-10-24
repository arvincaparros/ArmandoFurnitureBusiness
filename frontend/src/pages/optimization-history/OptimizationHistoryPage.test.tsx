import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import OptimizationHistoryPage from './OptimizationHistoryPage'
import { ThemeProvider } from '../../theme/ThemeContext'

import type { OptimizationHistory } from './types'
import useOptimizationHistory from './hooks/useOptimizationHistory'

vi.mock('./hooks/useOptimizationHistory', () => ({
  default: vi.fn(),
}))

// The chart is irrelevant to table pagination and Recharts needs
// measured dimensions jsdom does not provide.
vi.mock('./components/OptimizationHistoryChart', () => ({
  default: () => null,
}))

// Mirrors the newest-first order the hook returns: id N is newest.
const makeHistory = (count: number): OptimizationHistory[] =>
  Array.from({ length: count }, (_, index) => {
    const id = count - index

    return {
      id,
      optimizationId: `OP-${id}`,
      dateGenerated: '2026-10-04 15:45:13',
      duration: 600,
      totalProfit: 100000,
      totalProductionCost: 130000,
      productsProduced: 30,
    }
  })

const mockHistory = (runs: OptimizationHistory[]) => {
  vi.mocked(useOptimizationHistory).mockReturnValue({
    optimizationHistory: runs,
    profitTrendData: [],
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

    expect(screen.getAllByText(/^OP-\d+$/)).toHaveLength(10)
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
    expect(screen.getAllByText(/^OP-\d+$/)).toHaveLength(10)
    expect(screen.getByText('OP-25')).toBeInTheDocument()
    expect(screen.queryByText('OP-15')).not.toBeInTheDocument()

    const previous = screen.getByRole('button', { name: 'Previous' })
    const next = screen.getByRole('button', { name: 'Next' })

    expect(previous).toBeDisabled()
    expect(next).toBeEnabled()

    await user.click(next)

    expect(screen.getByText('Page 2 of 3')).toBeInTheDocument()
    expect(screen.getAllByText(/^OP-\d+$/)).toHaveLength(10)
    expect(screen.getByText('OP-15')).toBeInTheDocument()
    expect(screen.queryByText('OP-25')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeEnabled()

    await user.click(screen.getByRole('button', { name: 'Next' }))

    expect(screen.getByText('Page 3 of 3')).toBeInTheDocument()
    expect(screen.getAllByText(/^OP-\d+$/)).toHaveLength(5)
    expect(screen.getByText('OP-5')).toBeInTheDocument()
    expect(screen.getByText('OP-1')).toBeInTheDocument()
    expect(screen.queryByText('OP-6')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Previous' }))

    expect(screen.getByText('Page 2 of 3')).toBeInTheDocument()
    expect(screen.getByText('OP-15')).toBeInTheDocument()
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
    expect(screen.getByText('OP-26')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
  })
})

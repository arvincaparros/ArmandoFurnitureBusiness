import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ResourceUtilizationHistoryPage from './ResourceUtilizationHistoryPage'
import { ThemeProvider } from '../../theme/ThemeContext'

import type { UtilizationHistoryRow } from './types'
import useResourceUtilizationHistory from './hooks/useResourceUtilizationHistory'

vi.mock('./hooks/useResourceUtilizationHistory', () => ({
  default: vi.fn(),
}))

// Mirrors the newest-first order the hook returns: id N is newest.
const makeRows = (count: number): UtilizationHistoryRow[] =>
  Array.from({ length: count }, (_, index) => {
    const id = count - index

    return {
      id,
      utilizationNumber: `UT-${id}`,
      generatedAt: '2026-10-04 15:45:13',
      resourceName: `Resource ${id}`,
      unit: 'board ft',
      consumedQuantity: 10,
      remainingQuantity: 5,
      utilizationPercent: 60,
      status: 'normal',
    }
  })

const mockRows = (rows: UtilizationHistoryRow[]) => {
  vi.mocked(useResourceUtilizationHistory).mockReturnValue({
    rows,
    isLoading: false,
    isError: false,
  })
}

const pageUi = () => (
  <MantineProvider>
    <ThemeProvider>
      <ResourceUtilizationHistoryPage />
    </ThemeProvider>
  </MantineProvider>
)

const renderPage = () => render(pageUi())

beforeEach(() => {
  vi.mocked(useResourceUtilizationHistory).mockReset()
  mockRows([])
})

describe('ResourceUtilizationHistoryPage pagination', () => {
  it('renders the empty state without pagination controls', () => {
    renderPage()

    expect(
      screen.getByText(
        'No resource utilization history yet - apply a production plan to create the first snapshot.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Previous' }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Next' }),
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/^Page \d+ of \d+$/)).not.toBeInTheDocument()
  })

  it('shows all 15 rows and no controls when exactly one page exists', () => {
    mockRows(makeRows(15))

    renderPage()

    expect(screen.getAllByText(/^Resource \d+$/)).toHaveLength(15)
    expect(
      screen.queryByRole('button', { name: 'Previous' }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Next' }),
    ).not.toBeInTheDocument()
  })

  it('slices more than 15 rows into pages with bounded Previous/Next', async () => {
    const user = userEvent.setup()

    mockRows(makeRows(40))

    renderPage()

    expect(screen.getByText('Page 1 of 3')).toBeInTheDocument()
    expect(
      screen.getByText(
        '40 snapshots - created only when a production plan is applied',
      ),
    ).toBeInTheDocument()
    expect(screen.getAllByText(/^Resource \d+$/)).toHaveLength(15)
    expect(screen.getByText('Resource 40')).toBeInTheDocument()
    expect(screen.queryByText('Resource 25')).not.toBeInTheDocument()

    const previous = screen.getByRole('button', { name: 'Previous' })
    const next = screen.getByRole('button', { name: 'Next' })

    expect(previous).toBeDisabled()
    expect(next).toBeEnabled()

    await user.click(next)

    expect(screen.getByText('Page 2 of 3')).toBeInTheDocument()
    expect(screen.getAllByText(/^Resource \d+$/)).toHaveLength(15)
    expect(screen.getByText('Resource 25')).toBeInTheDocument()
    expect(screen.queryByText('Resource 40')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeEnabled()

    await user.click(screen.getByRole('button', { name: 'Next' }))

    expect(screen.getByText('Page 3 of 3')).toBeInTheDocument()
    expect(screen.getAllByText(/^Resource \d+$/)).toHaveLength(10)
    expect(screen.getByText('Resource 1')).toBeInTheDocument()
    expect(screen.queryByText('Resource 11')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Previous' }))

    expect(screen.getByText('Page 2 of 3')).toBeInTheDocument()
    expect(screen.getByText('Resource 25')).toBeInTheDocument()
  })

  it('returns to page 1 when the dataset grows', async () => {
    const user = userEvent.setup()

    mockRows(makeRows(40))

    const { rerender } = renderPage()

    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('button', { name: 'Next' }))

    expect(screen.getByText('Page 3 of 3')).toBeInTheDocument()

    // Simulate a refetch after a new snapshot (40 -> 41 rows).
    mockRows(makeRows(41))

    rerender(pageUi())

    expect(screen.getByText('Page 1 of 3')).toBeInTheDocument()
    expect(screen.getByText('Resource 41')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
  })

  it('keeps pagination in range when the dataset shrinks', async () => {
    const user = userEvent.setup()

    mockRows(makeRows(40))

    const { rerender } = renderPage()

    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('button', { name: 'Next' }))

    expect(screen.getByText('Page 3 of 3')).toBeInTheDocument()

    mockRows(makeRows(16))

    rerender(pageUi())

    expect(screen.getByText('Page 1 of 2')).toBeInTheDocument()
    expect(screen.getAllByText(/^Resource \d+$/)).toHaveLength(15)
    expect(screen.getByText('Resource 16')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled()
  })
})

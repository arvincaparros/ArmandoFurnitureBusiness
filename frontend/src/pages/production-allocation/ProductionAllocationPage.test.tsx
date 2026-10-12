import { render, screen, waitFor } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ProductionAllocationPage from './ProductionAllocationPage'
import { ThemeProvider } from '../../theme/ThemeContext'
import { fetchFeasibility } from './api/productionApi'

vi.mock('../../hooks/useLatestProductionCycle', () => ({
  default: () => ({ cycleId: 1, hasCycle: true, isLoading: false, isError: false }),
}))

vi.mock('./api/productionApi', () => ({
  fetchOptimizationHistory: vi.fn().mockResolvedValue([]),
  fetchProductSummaries: vi.fn().mockResolvedValue([]),
  fetchProductionAllocations: vi.fn().mockResolvedValue([
    { id: 1, production_cycle_id: 1, product_id: 1, quantity: '12', total_revenue: '1000', total_cost: '500', total_profit: '500' },
  ]),
  fetchFeasibility: vi.fn(),
  runOptimization: vi.fn(),
  applyOptimization: vi.fn(),
}))

beforeEach(() => {
  vi.mocked(fetchFeasibility).mockReset()

  vi.mocked(fetchFeasibility).mockResolvedValue({
    cycle_id: 1,
    is_feasible: false,
    resources: [],
    bottlenecks: [
      { resource_id: 1, resource_name: 'Wood', unit: 'board ft', shortage_quantity: '189' },
    ],
    needs_reoptimization: true,
    applied_at: '2026-10-01T00:00:00',
  })
})

const renderPage = () => {
  const queryClient = new QueryClient()

  return render(
    <MantineProvider>
      <Notifications />
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <ProductionAllocationPage />
        </QueryClientProvider>
      </ThemeProvider>
    </MantineProvider>,
  )
}

describe('ProductionAllocationPage re-optimization status', () => {
  it('shows a Needs Review - Resource Shortage banner with the shortage amount', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText(/needs re-optimization/i)).toBeInTheDocument()
    })

    expect(
      screen.getByText('Needs Review — Resource Shortage'),
    ).toBeInTheDocument()
    expect(screen.getByText(/wood/i)).toBeInTheDocument()
    expect(screen.getByText(/189/)).toBeInTheDocument()
  })

  it('shows a Needs Re-optimization banner when still feasible but stale, with no shortage text', async () => {
    vi.mocked(fetchFeasibility).mockResolvedValueOnce({
      cycle_id: 1,
      is_feasible: true,
      resources: [],
      bottlenecks: [],
      needs_reoptimization: true,
      applied_at: '2026-10-01T00:00:00',
    })

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Needs Re-optimization')).toBeInTheDocument()
    })

    expect(screen.queryByText(/short by/i)).not.toBeInTheDocument()
  })
})

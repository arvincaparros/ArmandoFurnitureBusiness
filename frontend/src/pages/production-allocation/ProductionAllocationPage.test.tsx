import { render, screen, waitFor, within } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ProductionAllocationPage from './ProductionAllocationPage'
import { ThemeProvider } from '../../theme/ThemeContext'
import {
  fetchFeasibility,
  fetchOptimizationHistory,
  fetchProductionApplications,
  runOptimization,
} from './api/productionApi'

vi.mock('../../hooks/useLatestProductionCycle', () => ({
  default: () => ({ cycleId: 1, hasCycle: true, isLoading: false, isError: false }),
}))

vi.mock('./api/productionApi', () => ({
  fetchOptimizationHistory: vi.fn().mockResolvedValue([]),
  fetchProductSummaries: vi.fn().mockResolvedValue([]),
  fetchProductionAllocations: vi.fn().mockResolvedValue([
    { id: 1, production_cycle_id: 1, product_id: 1, quantity: '12', total_revenue: '1000', total_cost: '500', total_profit: '500' },
  ]),
  fetchProductionApplications: vi.fn().mockResolvedValue([]),
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


describe('ProductionAllocationPage additive apply', () => {
  it('tells the user Apply will add to this cycle, not replace it', async () => {
    // A latest OPTIMAL run is required for Apply to be enabled.
    vi.mocked(fetchOptimizationHistory).mockResolvedValueOnce([
      {
        id: 7,
        status: 'OPTIMAL',
        is_summary_only: false,
        results: [
          {
            product_id: 1,
            recommended_quantity: '10.0000',
            unit_profit: '100.0000',
            total_profit: '1000.0000',
          },
        ],
      },
    ] as never)

    renderPage()

    // The page swaps the DISABLED Tooltip-wrapped button for an
    // enabled one once a latest OPTIMAL run resolves, so the element
    // has to be re-queried after it becomes enabled - a node captured
    // beforehand is detached by that swap and clicking it does
    // nothing.
    await waitFor(() => {
      expect(
        screen.getByRole('button', {
          name: /apply to production/i,
        }),
      ).toBeEnabled()
    })

    await userEvent.click(
      screen.getByRole('button', {
        name: /apply to production/i,
      }),
    )

    expect(
      await screen.findByText(/add .* to this cycle/i),
    ).toBeInTheDocument()

    expect(
      screen.queryByText(
        /replace the current committed allocation/i,
      ),
    ).not.toBeInTheDocument()
  })

})

const openGenerateModal = async () => {
  await userEvent.click(
    screen.getByRole('button', {
      name: /generate optimal production plan/i,
    }),
  )

  expect(
    await screen.findByRole('heading', {
      name: 'Generate Production Plan',
    }),
  ).toBeInTheDocument()
}

describe('ProductionAllocationPage generate mode modal', () => {
  it('opens the modal instead of generating immediately, with Demand-Based selected by default', async () => {
    renderPage()

    expect(runOptimization).not.toHaveBeenCalled()

    await openGenerateModal()

    expect(
      screen.getByRole('radio', { name: /demand-based optimization/i }),
    ).toBeChecked()

    expect(
      screen.getByRole('radio', { name: /resource-based optimization/i }),
    ).not.toBeChecked()

    // Opening the modal alone must never fire a request.
    expect(runOptimization).not.toHaveBeenCalled()
  })

  it('switches the checked option when Resource-Based is selected', async () => {
    renderPage()

    await openGenerateModal()

    await userEvent.click(
      screen.getByRole('radio', { name: /resource-based optimization/i }),
    )

    expect(
      screen.getByRole('radio', { name: /resource-based optimization/i }),
    ).toBeChecked()

    expect(
      screen.getByRole('radio', { name: /demand-based optimization/i }),
    ).not.toBeChecked()
  })

  it('Cancel closes the modal without calling the API', async () => {
    renderPage()

    await openGenerateModal()

    await userEvent.click(
      screen.getByRole('radio', { name: /resource-based optimization/i }),
    )

    await userEvent.click(
      screen.getByRole('button', { name: 'Cancel' }),
    )

    await waitFor(() => {
      expect(
        screen.queryByRole('heading', {
          name: 'Generate Production Plan',
        }),
      ).not.toBeInTheDocument()
    })

    expect(runOptimization).not.toHaveBeenCalled()
  })

  it('preserves the selected mode the next time the modal is reopened', async () => {
    renderPage()

    await openGenerateModal()

    await userEvent.click(
      screen.getByRole('radio', { name: /resource-based optimization/i }),
    )

    await userEvent.click(
      screen.getByRole('button', { name: 'Cancel' }),
    )

    await waitFor(() => {
      expect(
        screen.queryByRole('heading', {
          name: 'Generate Production Plan',
        }),
      ).not.toBeInTheDocument()
    })

    await openGenerateModal()

    expect(
      screen.getByRole('radio', { name: /resource-based optimization/i }),
    ).toBeChecked()
  })

  it('Continue sends the default Demand-Based mode, closes the modal, and shows it in the result', async () => {
    vi.mocked(runOptimization).mockResolvedValueOnce({
      cycle_id: 1,
      status: 'OPTIMAL',
      objective: 'MAX_PROFIT',
      planning_mode: 'demand_based',
      total_revenue: '1000',
      total_cost: '500',
      total_profit: '500',
      allocations: [],
    })

    renderPage()

    await openGenerateModal()

    await userEvent.click(
      screen.getByRole('button', { name: 'Continue' }),
    )

    await waitFor(() => {
      expect(
        screen.queryByRole('heading', {
          name: 'Generate Production Plan',
        }),
      ).not.toBeInTheDocument()
    })

    expect(runOptimization).toHaveBeenCalledTimes(1)
    expect(runOptimization).toHaveBeenCalledWith(1, 'demand_based')

    const modeRow = (await screen.findByText('Mode')).closest('div')

    expect(
      within(modeRow!).getByText('Demand-Based'),
    ).toBeInTheDocument()
  })

  it('Continue sends Resource-Based once selected, and shows it in the result', async () => {
    vi.mocked(runOptimization).mockResolvedValueOnce({
      cycle_id: 1,
      status: 'OPTIMAL',
      objective: 'MAX_PROFIT',
      planning_mode: 'resource_based',
      total_revenue: '1000',
      total_cost: '500',
      total_profit: '500',
      allocations: [],
    })

    renderPage()

    await openGenerateModal()

    await userEvent.click(
      screen.getByRole('radio', { name: /resource-based optimization/i }),
    )

    await userEvent.click(
      screen.getByRole('button', { name: 'Continue' }),
    )

    await waitFor(() => {
      expect(runOptimization).toHaveBeenCalledWith(1, 'resource_based')
    })

    const modeRow = (await screen.findByText('Mode')).closest('div')

    expect(
      within(modeRow!).getByText('Resource-Based'),
    ).toBeInTheDocument()
  })

  it('never fires more than one request even if Continue is clicked repeatedly', async () => {
    vi.mocked(runOptimization).mockResolvedValueOnce({
      cycle_id: 1,
      status: 'OPTIMAL',
      objective: 'MAX_PROFIT',
      planning_mode: 'demand_based',
      total_revenue: '1000',
      total_cost: '500',
      total_profit: '500',
      allocations: [],
    })

    renderPage()

    await openGenerateModal()

    const continueButton = screen.getByRole('button', { name: 'Continue' })

    await userEvent.click(continueButton)
    await userEvent.click(continueButton)
    await userEvent.click(continueButton)

    await waitFor(() => {
      expect(runOptimization).toHaveBeenCalledTimes(1)
    })
  })
})

describe('ProductionAllocationPage already-applied plan', () => {
  it('explains why Apply is unavailable for an already-applied plan', async () => {
    vi.mocked(fetchOptimizationHistory).mockResolvedValueOnce([
      {
        id: 7,
        status: 'OPTIMAL',
        is_summary_only: false,
        results: [
          {
            product_id: 1,
            recommended_quantity: '10.0000',
            unit_profit: '100.0000',
            total_profit: '1000.0000',
          },
        ],
      },
    ] as never)

    vi.mocked(fetchProductionApplications).mockResolvedValueOnce([
      {
        id: 1,
        application_number: 'PA-0001',
        production_cycle_id: 1,
        optimization_run_id: 7,
        applied_at: '2026-10-30T09:00:00',
        product_items: [
          { product_id: 1, quantity_produced: '10.0000' },
        ],
        resource_items: [],
      },
    ] as never)

    renderPage()

    expect(
      await screen.findByText(/already been applied/i),
    ).toBeInTheDocument()
  })
})

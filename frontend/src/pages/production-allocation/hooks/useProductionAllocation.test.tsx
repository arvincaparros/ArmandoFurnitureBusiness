import {
  act,
  renderHook,
  waitFor,
} from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'

import useProductionAllocation from './useProductionAllocation'
import {
  applyOptimization,
  fetchOptimizationHistory,
  fetchProductionApplications,
} from '../api/productionApi'

vi.mock('../../../hooks/useLatestProductionCycle', () => ({
  default: () => ({
    cycleId: 1,
    hasCycle: true,
    isLoading: false,
    isError: false,
  }),
}))

vi.mock('../api/productionApi', () => ({
  fetchOptimizationHistory: vi.fn().mockResolvedValue([]),
  fetchProductSummaries: vi.fn().mockResolvedValue([]),
  fetchProductionAllocations: vi.fn().mockResolvedValue([]),
  fetchProductionApplications: vi.fn().mockResolvedValue([]),
  fetchFeasibility: vi.fn().mockResolvedValue({
    cycle_id: 1,
    is_feasible: true,
    resources: [],
    bottlenecks: [],
    needs_reoptimization: false,
    applied_at: null,
  }),
  runOptimization: vi.fn(),
  applyOptimization: vi.fn().mockResolvedValue({
    cycle_id: 1,
    status: 'OPTIMAL',
    objective: 'MAX_PROFIT',
    total_revenue: '0',
    total_cost: '0',
    total_profit: '0',
    allocations: [],
  }),
}))

describe('useProductionAllocation apply cache invalidation', () => {
  it('invalidates the demand forecasting queries after a successful apply', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    })

    const invalidateSpy = vi.spyOn(
      queryClient,
      'invalidateQueries',
    )

    const { result } = renderHook(
      () => useProductionAllocation(),
      {
        wrapper: ({ children }) => (
          <QueryClientProvider client={queryClient}>
            {children}
          </QueryClientProvider>
        ),
      },
    )

    await act(async () => {
      await result.current.applyToProduction()
    })

    expect(applyOptimization).toHaveBeenCalledWith(1)

    // Apply doesn't create sales history (see app/services/
    // forecasting.py::get_forecast), but both demand-forecasting
    // queries must still be invalidated so the page refetches instead
    // of serving a cached pre-apply view.
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ['forecast'],
    })
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ['forecast-timeseries'],
    })
  })

  // --- Task 16 -----------------------------------------------------

  it('invalidates the inventory query after a successful apply', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(
      () => useProductionAllocation(),
      {
        wrapper: ({ children }) => (
          <QueryClientProvider client={queryClient}>
            {children}
          </QueryClientProvider>
        ),
      },
    )

    await act(async () => {
      await result.current.applyToProduction()
    })

    // Shared key: the Inventory page and the Add Transaction modal
    // both read stock through ['inventory'].
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ['inventory'],
    })
  })

  it('reports the current plan as already applied and blocks Apply', async () => {
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
        // Must match the run id findLatestOptimalRun resolves from
        // the mocked history above.
        optimization_run_id: 7,
        applied_at: '2026-10-30T09:00:00',
        product_items: [
          { product_id: 1, quantity_produced: '10.0000' },
        ],
        resource_items: [],
      },
    ] as never)

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    const { result } = renderHook(
      () => useProductionAllocation(),
      {
        wrapper: ({ children }) => (
          <QueryClientProvider client={queryClient}>
            {children}
          </QueryClientProvider>
        ),
      },
    )

    await waitFor(() => {
      expect(result.current.isCurrentPlanApplied).toBe(true)
    })

    expect(result.current.canApply).toBe(false)
  })
})

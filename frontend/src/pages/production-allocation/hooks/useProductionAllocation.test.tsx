import { act, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'

import useProductionAllocation from './useProductionAllocation'
import { applyOptimization } from '../api/productionApi'

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
})

import apiClient from '../../../api/client'

import type {
  DashboardSummaryResponse,
  OptimizationHistoryResponse,
  ProductSummary,
  ProductionAllocationFinancials,
  ResourceUtilizationResponse,
} from './dashboardTypes'

export async function fetchDashboardSummary(): Promise<DashboardSummaryResponse> {
  const response = await apiClient.get<DashboardSummaryResponse>(
    '/api/dashboard/summary',
  )

  return response.data
}

// Scoped to the canonical latest production cycle (resolved via the
// shared useLatestProductionCycle() hook, not re-derived here) so
// this can never surface a different cycle's recommendation than
// what Production Allocation/Resource Utilization are showing - see
// the Dashboard Latest-Cycle Optimization Scoping report. /history
// is ordered newest-first even within one cycle (verified in
// backend/app/services/optimization_history.py), so the caller
// still picks the first OPTIMAL entry itself. include_hidden stays
// as a defensive option so a caller that must operate on the live
// plan is never blinded by a hidden run; the approved Optimization
// History cleanup leaves every row visible, so it has no effect
// today. See dashboardAdapter.ts.
export async function fetchOptimizationHistory(
  cycleId: number,
  includeHidden = false,
): Promise<OptimizationHistoryResponse[]> {
  const response = await apiClient.get<OptimizationHistoryResponse[]>(
    '/api/optimization/history',
    {
      params: {
        cycle_id: cycleId,
        ...(includeHidden ? { include_hidden: true } : {}),
      },
    },
  )

  return response.data
}

// GET /api/resource-utilization (no cycle_id) returns the latest
// production cycle's utilization, or 404 if no cycle exists yet -
// that 404 is a legitimate empty state here, not a failure.
export async function fetchLatestResourceUtilization(): Promise<
  ResourceUtilizationResponse | null
> {
  try {
    const response = await apiClient.get<ResourceUtilizationResponse>(
      '/api/resource-utilization',
    )

    return response.data
  } catch (error) {
    if (
      typeof error === 'object' &&
      error !== null &&
      'response' in error &&
      (error as { response?: { status?: number } }).response
        ?.status === 404
    ) {
      return null
    }

    throw error
  }
}

// Used only to resolve product_id -> name for the recommendations
// table - the optimization history endpoint doesn't include names
// (same gap pattern as the forecast history endpoints).
export async function fetchProductSummaries(): Promise<
  ProductSummary[]
> {
  const response = await apiClient.get<ProductSummary[]>(
    '/api/products',
  )

  return response.data
}

// The committed production allocation for a cycle - the Dashboard's
// fallback source for the two financial stat cards when no usable
// optimization run exists (e.g. right after the approved Optimization
// History cleanup deletes the old test runs). Shares its query key
// with useProductionAllocation, so both pages read one cached copy
// and an Apply there refreshes this one too.
export async function fetchProductionAllocations(
  cycleId: number,
): Promise<ProductionAllocationFinancials[]> {
  const response = await apiClient.get<
    ProductionAllocationFinancials[]
  >(`/api/production-cycles/${cycleId}/allocations`)

  return response.data
}

import apiClient from '../../../api/client'

import type {
  DashboardSummaryResponse,
  OptimizationHistoryResponse,
  ProductSummary,
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
// still picks the first OPTIMAL entry itself. See dashboardAdapter.ts.
export async function fetchOptimizationHistory(
  cycleId: number,
): Promise<OptimizationHistoryResponse[]> {
  const response = await apiClient.get<OptimizationHistoryResponse[]>(
    '/api/optimization/history',
    { params: { cycle_id: cycleId } },
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

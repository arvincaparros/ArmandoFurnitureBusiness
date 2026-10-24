import apiClient from '../../../api/client'

import type {
  OptimizationHistoryResponse,
  OptimizationResponse,
  ProductionAllocationResponse,
  ProductionFeasibilityResponse,
  ProductSummary,
} from './productionTypes'

// "Latest production cycle" resolution now comes from the shared
// ../../../hooks/useLatestProductionCycle (GET
// /api/production-cycles/latest) instead of fetching the whole list
// here - see the Production Cycle Selection Consistency Audit.

// include_hidden=true is this page's own choice: a page that
// previews and applies the live plan must never be blinded if a run
// is hidden from Optimization History. The approved cleanup leaves
// every row visible, so it has no effect today. The backend still
// resolves "latest" itself on Apply, so the flag only affects which
// runs this page can see. Summary-only records are filtered out in
// productionAdapter.ts::findLatestOptimalRun.
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

export async function runOptimization(
  cycleId: number,
): Promise<OptimizationResponse> {
  const response = await apiClient.post<OptimizationResponse>(
    `/api/production-cycles/${cycleId}/optimize`,
    { objective: 'MAX_PROFIT' },
  )

  return response.data
}

// Commits the latest OPTIMAL optimization run into
// ProductionAllocation - the backend resolves "latest" itself
// (get_latest_optimization_history_run), so this always applies
// whatever the backend currently considers current, not a
// frontend-held snapshot. No request body - the router takes only
// cycle_id.
export async function applyOptimization(
  cycleId: number,
): Promise<OptimizationResponse> {
  const response = await apiClient.post<OptimizationResponse>(
    `/api/production-cycles/${cycleId}/optimize/apply`,
  )

  return response.data
}

export async function fetchProductSummaries(): Promise<
  ProductSummary[]
> {
  const response = await apiClient.get<ProductSummary[]>(
    '/api/products',
  )

  return response.data
}

// The actual committed allocation for a cycle - read-only in this
// integration, see the integration report for why no create/update/
// delete UI was added despite the backend supporting full CRUD here.
export async function fetchProductionAllocations(
  cycleId: number,
): Promise<ProductionAllocationResponse[]> {
  const response = await apiClient.get<
    ProductionAllocationResponse[]
  >(`/api/production-cycles/${cycleId}/allocations`)

  return response.data
}

export async function fetchFeasibility(
  cycleId: number,
): Promise<ProductionFeasibilityResponse> {
  const response = await apiClient.get<ProductionFeasibilityResponse>(
    `/api/production-cycles/${cycleId}/feasibility`,
  )

  return response.data
}

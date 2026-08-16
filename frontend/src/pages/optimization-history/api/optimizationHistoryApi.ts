import apiClient from '../../../api/client'

import type { OptimizationHistoryRunResponse } from './optimizationHistoryTypes'

// Deliberately NOT scoped to a cycle_id, unlike Dashboard/Production
// Allocation's use of this same endpoint - this page is an explicit
// cross-cycle historical log ("Stored previous optimization results...
// for future reference", per its own subtitle), not a current-cycle
// widget, so every past run across every cycle is intentionally
// included. See the Optimization History integration report.
export async function fetchOptimizationHistory(): Promise<
  OptimizationHistoryRunResponse[]
> {
  const response = await apiClient.get<
    OptimizationHistoryRunResponse[]
  >('/api/optimization/history')

  return response.data
}

// Same real workflow Production Allocation's "Generate Optimal
// Production Plan" button already uses (production-allocation/api/
// productionApi.ts::runOptimization) - identical endpoint and request
// body. This computes AND persists a new optimization run
// (app/services/optimization.py calls save_optimization_history
// internally) but does NOT write ProductionAllocation - only POST
// .../optimize/apply does that, and nothing here calls it, so
// "Run Manual Optimization" can never auto-commit a plan. Kept as a
// local copy rather than importing production-allocation/api/
// productionApi.ts, matching this project's established convention
// of not cross-importing between page modules (the same pattern
// already used for fetchProductSummaries, duplicated locally in
// Dashboard/Production Allocation/Transaction History/Demand
// Forecasting) - same endpoint, same request shape, not a
// reimplementation of the optimization algorithm. The response body
// isn't needed here: the caller invalidates the history query and
// lets it refetch, rather than eagerly merging this response.
export async function runOptimization(
  cycleId: number,
): Promise<void> {
  await apiClient.post(
    `/api/production-cycles/${cycleId}/optimize`,
    { objective: 'MAX_PROFIT' },
  )
}

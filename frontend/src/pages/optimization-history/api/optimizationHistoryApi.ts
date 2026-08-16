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

import apiClient from '../../../api/client'

import type {
  ResourceUtilizationRunResponse,
  ResourceUtilizationRunSummaryResponse,
} from './utilizationHistoryTypes'

// GET /api/resource-utilization/history - snapshots created only
// when "Apply to Production" succeeds (never by generating a plan
// preview). Optionally scoped to one cycle; omitted here since this
// page shows history across all cycles, matching Optimization
// History's own unscoped GET /api/optimization/history.
export async function fetchResourceUtilizationHistory(): Promise<
  ResourceUtilizationRunSummaryResponse[]
> {
  const response = await apiClient.get<
    ResourceUtilizationRunSummaryResponse[]
  >('/api/resource-utilization/history')

  return response.data
}

export async function fetchResourceUtilizationHistoryDetail(
  runId: number,
): Promise<ResourceUtilizationRunResponse> {
  const response = await apiClient.get<ResourceUtilizationRunResponse>(
    `/api/resource-utilization/history/${runId}`,
  )

  return response.data
}

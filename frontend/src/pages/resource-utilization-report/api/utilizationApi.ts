import apiClient from '../../../api/client'

import type { ResourceUtilizationResponse } from './utilizationTypes'

// "Latest production cycle" resolution now comes from the shared
// ../../../hooks/useLatestProductionCycle (GET
// /api/production-cycles/latest) instead of fetching the whole list
// here - see the Production Cycle Selection Consistency Audit. This
// module always calls the cycle-specific endpoint below with an
// explicit id, never the no-arg /api/resource-utilization.

export async function fetchResourceUtilization(
  cycleId: number,
): Promise<ResourceUtilizationResponse> {
  const response = await apiClient.get<ResourceUtilizationResponse>(
    `/api/resource-utilization/${cycleId}`,
  )

  return response.data
}

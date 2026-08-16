import apiClient from '../../../api/client'

import type { CycleResourceResponse } from './cycleResourceTypes'

// Resource unit prices are NOT fields on the global Resource record
// (backend/app/database/models.py - Resource has no price column).
// They live on CycleResource, scoped to a production cycle. This is
// the same GET /api/production-cycles/{cycleId}/resources endpoint
// and the same ['cycle-resources', cycleId] query key used by
// resources-management/api/cycleResourceApi.ts, shared verbatim so
// React Query dedupes the fetch and a pricing edit made on the
// Resources page invalidates this module's cost calculation too -
// the same pattern already used for 'resources-all' between this
// page and Product Resource Requirements.
export async function fetchCycleResources(
  cycleId: number,
): Promise<CycleResourceResponse[]> {
  const response = await apiClient.get<CycleResourceResponse[]>(
    `/api/production-cycles/${cycleId}/resources`,
  )

  return response.data
}

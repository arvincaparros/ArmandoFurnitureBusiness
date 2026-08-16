import apiClient from '../../../api/client'

import type {
  CycleResourceCreateRequest,
  CycleResourceResponse,
  CycleResourceUpdateRequest,
} from './cycleResourceTypes'

// Resource availability and unit price are NOT fields on the global
// Resource record (backend/app/database/models.py - Resource has no
// price/quantity column). They live on CycleResource, scoped to a
// production cycle. This page surfaces them for the latest
// production cycle - the same canonical resolution Production
// Allocation and Resource Utilization already use via
// useLatestProductionCycle - as this resource's "current"
// availability/price, per the approved business model, without
// changing the backend schema.
//
// Uses the same ['cycle-resources', cycleId] query key as
// product-data-management/api/cycleResourceApi.ts (shared verbatim,
// same convention as 'resources-all' elsewhere in this app) so a
// pricing edit made here invalidates that module's cost calculation
// too.
export async function fetchCycleResources(
  cycleId: number,
): Promise<CycleResourceResponse[]> {
  const response = await apiClient.get<CycleResourceResponse[]>(
    `/api/production-cycles/${cycleId}/resources`,
  )

  return response.data
}

export async function createCycleResource(
  cycleId: number,
  data: CycleResourceCreateRequest,
): Promise<CycleResourceResponse> {
  const response = await apiClient.post<CycleResourceResponse>(
    `/api/production-cycles/${cycleId}/resources`,
    data,
  )

  return response.data
}

export async function updateCycleResource(
  cycleId: number,
  resourceId: number,
  data: CycleResourceUpdateRequest,
): Promise<CycleResourceResponse> {
  const response = await apiClient.patch<CycleResourceResponse>(
    `/api/production-cycles/${cycleId}/resources/${resourceId}`,
    data,
  )

  return response.data
}

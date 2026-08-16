import apiClient from '../../../api/client'

import type {
  ResourceCreateRequest,
  ResourceResponse,
  ResourceUpdateRequest,
} from './resourceTypes'

// include_inactive is supported by the backend but not exposed here -
// the current Resources UI has no active/inactive concept anywhere
// (no toggle, no status column, no filter), so this always uses the
// default (active-only) listing to preserve existing UX exactly.
export async function fetchResources(): Promise<ResourceResponse[]> {
  const response = await apiClient.get<ResourceResponse[]>(
    '/api/resources',
  )

  return response.data
}

export async function createResource(
  data: ResourceCreateRequest,
): Promise<ResourceResponse> {
  const response = await apiClient.post<ResourceResponse>(
    '/api/resources',
    data,
  )

  return response.data
}

export async function updateResource(
  id: number,
  data: ResourceUpdateRequest,
): Promise<ResourceResponse> {
  const response = await apiClient.patch<ResourceResponse>(
    `/api/resources/${id}`,
    data,
  )

  return response.data
}

// Backend soft-deletes (sets is_active = false) rather than
// removing the row - see backend/app/services/resource.py. Since
// the default list fetch is active-only, the effect after
// invalidation is identical to the old hard-delete-from-array mock
// behavior: the row disappears from the table.
export async function deleteResource(id: number): Promise<void> {
  await apiClient.delete(`/api/resources/${id}`)
}

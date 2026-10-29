import apiClient from '../../../api/client'

import type {
  ResourceCreateRequest,
  ResourceResponse,
  ResourceUpdateRequest,
} from './resourceTypes'

// include_inactive is supported by the backend but not exposed here -
// this call backs the Active view of the Resources table, so it uses
// the default (active-only) listing. The page's Inactive view and the
// Add Resource selector use fetchAllResourcesIncludingInactive below
// instead, and reactivation PATCHes is_active on the existing row via
// updateResource, so this listing reflects the change on its next
// fetch.
export async function fetchResources(): Promise<ResourceResponse[]> {
  const response = await apiClient.get<ResourceResponse[]>(
    '/api/resources',
  )

  return response.data
}

// POST /api/resources - used by the Add Resource form's "Create New"
// mode only (see AddResourceModal.tsx and useResources.ts). Its "Use
// Existing" mode never calls this: that assigns an already-catalogued
// resource to the latest production cycle via CycleResource, so an
// existing resource keeps its own id and is never duplicated.
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

// DELETE /api/resources/{id}/permanent - a DIFFERENT endpoint from
// deleteResource above, which still soft-deletes. This one removes
// the catalogue row outright and is irreversible.
//
// The backend refuses with 409 (never a silent partial delete) when
// the resource is still active, or when a product resource
// requirement or a production cycle's availability/pricing still
// references it; the detail names exactly what is blocking, so
// callers should surface it rather than a generic message (see
// getApiErrorMessage). Resource utilization history never blocks:
// those rows keep their own snapshotted resource name/type/unit and
// survive the delete intact.
export async function permanentlyDeleteResource(
  id: number,
): Promise<void> {
  await apiClient.delete(`/api/resources/${id}/permanent`)
}

// Same GET /api/resources?include_inactive=true endpoint and
// 'resources-all' query key already used by product-data-management/
// api/productResourceApi.ts's fetchAllResourcesForPicker() - a local
// copy (not a cross-module import, matching this app's existing
// per-module convention - see that file's own comment), but sharing
// the identical query key so a fetch made by either module's page
// satisfies both, the same cache-sharing pattern already used for
// 'cycle-resources'. Used by the Add Resource form's "Use Existing"
// Name select (see AddResourceModal.tsx), which lists every resource
// with an Active/Inactive badge and never offers an unlisted/create-
// new option there, and by its "Create New" mode to block a name that
// another resource already has - no filtering happens here, so this
// stays a plain mirror of the backend response.
export async function fetchAllResourcesIncludingInactive(): Promise<
  ResourceResponse[]
> {
  const response = await apiClient.get<ResourceResponse[]>(
    '/api/resources',
    { params: { include_inactive: true } },
  )

  return response.data
}

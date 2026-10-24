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

// Mirror of POST /api/resources. The Resources page itself no longer
// creates catalog entries - its Add Resource form only assigns an
// already-existing resource to the latest production cycle via
// CycleResource (see AddResourceModal.tsx and useResources.ts). Kept
// here as the faithful API mirror for any future admin workflow; no
// current page imports it.
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

// Same GET /api/resources?include_inactive=true endpoint and
// 'resources-all' query key already used by product-data-management/
// api/productResourceApi.ts's fetchAllResourcesForPicker() - a local
// copy (not a cross-module import, matching this app's existing
// per-module convention - see that file's own comment), but sharing
// the identical query key so a fetch made by either module's page
// satisfies both, the same cache-sharing pattern already used for
// 'cycle-resources'. Used by the Add Resource form's Name select
// (see AddResourceModal.tsx), which lists every resource with an
// Active/Inactive badge and never offers an unlisted/create-new
// option - no filtering happens here, so this stays a plain mirror
// of the backend response.
export async function fetchAllResourcesIncludingInactive(): Promise<
  ResourceResponse[]
> {
  const response = await apiClient.get<ResourceResponse[]>(
    '/api/resources',
    { params: { include_inactive: true } },
  )

  return response.data
}

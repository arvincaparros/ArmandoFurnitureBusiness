import apiClient from '../../../api/client'

import type {
  OpeningInventorySetCreateRequest,
  OpeningInventorySetResponse,
  OpeningInventorySetUpdateRequest,
  OpeningInventoryStatusResponse,
} from './openingInventoryTypes'

export async function fetchOpeningInventorySets(): Promise<
  OpeningInventorySetResponse[]
> {
  const response = await apiClient.get<
    OpeningInventorySetResponse[]
  >('/api/opening-inventory')

  return response.data
}

export async function fetchOpeningInventoryStatus(): Promise<
  OpeningInventoryStatusResponse
> {
  const response = await apiClient.get<
    OpeningInventoryStatusResponse
  >('/api/opening-inventory/active')

  return response.data
}

export async function createOpeningInventorySet(
  data: OpeningInventorySetCreateRequest,
): Promise<OpeningInventorySetResponse> {
  const response = await apiClient.post<
    OpeningInventorySetResponse
  >('/api/opening-inventory', data)

  return response.data
}

export async function updateOpeningInventorySet(
  setId: number,
  data: OpeningInventorySetUpdateRequest,
): Promise<OpeningInventorySetResponse> {
  const response = await apiClient.patch<
    OpeningInventorySetResponse
  >(`/api/opening-inventory/${setId}`, data)

  return response.data
}

// Flips DRAFT -> REVIEWED and supersedes any previously reviewed set.
// No request body - the router takes only set_id and reads the
// reviewer from the auth token.
export async function reviewOpeningInventorySet(
  setId: number,
): Promise<OpeningInventorySetResponse> {
  const response = await apiClient.post<
    OpeningInventorySetResponse
  >(`/api/opening-inventory/${setId}/review`)

  return response.data
}

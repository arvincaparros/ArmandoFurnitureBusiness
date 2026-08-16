import apiClient from '../../../api/client'

import type {
  ProductResourceRequirementCreateRequest,
  ProductResourceRequirementResponse,
  ProductResourceRequirementUpdateRequest,
  ResourceOption,
} from './productResourceTypes'

export async function fetchProductResourceRequirements(
  productId: number,
): Promise<ProductResourceRequirementResponse[]> {
  const response = await apiClient.get<
    ProductResourceRequirementResponse[]
  >(`/api/products/${productId}/resources`)

  return response.data
}

export async function createProductResourceRequirement(
  productId: number,
  data: ProductResourceRequirementCreateRequest,
): Promise<ProductResourceRequirementResponse> {
  const response = await apiClient.post<
    ProductResourceRequirementResponse
  >(`/api/products/${productId}/resources`, data)

  return response.data
}

export async function updateProductResourceRequirement(
  productId: number,
  resourceId: number,
  data: ProductResourceRequirementUpdateRequest,
): Promise<ProductResourceRequirementResponse> {
  const response = await apiClient.patch<
    ProductResourceRequirementResponse
  >(`/api/products/${productId}/resources/${resourceId}`, data)

  return response.data
}

export async function deleteProductResourceRequirement(
  productId: number,
  resourceId: number,
): Promise<void> {
  await apiClient.delete(
    `/api/products/${productId}/resources/${resourceId}`,
  )
}

// include_inactive=true so existing requirements pointing at a
// since-deactivated resource can still resolve their display info
// (name/unit) - the picker for NEW requirements filters this list
// down to is_active resources itself, client-side. See the
// architecture analysis's §7 for why inactive resources must stay
// visible on existing requirements but not be newly selectable.
export async function fetchAllResourcesForPicker(): Promise<
  ResourceOption[]
> {
  const response = await apiClient.get<ResourceOption[]>(
    '/api/resources',
    { params: { include_inactive: true } },
  )

  return response.data
}

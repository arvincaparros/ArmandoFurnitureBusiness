import apiClient from '../../../api/client'

import type {
  ProductCreateRequest,
  ProductResponse,
  ProductUpdateRequest,
} from './productTypes'

// include_inactive is supported by the backend but not exposed here -
// the current Products UI has no active/inactive concept anywhere
// (no toggle, no status column, no filter), matching the same
// decision made for Resources - default (active-only) listing
// preserves existing UX exactly.
export async function fetchProducts(): Promise<ProductResponse[]> {
  const response = await apiClient.get<ProductResponse[]>(
    '/api/products',
  )

  return response.data
}

export async function createProduct(
  data: ProductCreateRequest,
): Promise<ProductResponse> {
  const response = await apiClient.post<ProductResponse>(
    '/api/products',
    data,
  )

  return response.data
}

export async function updateProduct(
  id: number,
  data: ProductUpdateRequest,
): Promise<ProductResponse> {
  const response = await apiClient.patch<ProductResponse>(
    `/api/products/${id}`,
    data,
  )

  return response.data
}

// Backend soft-deletes (sets is_active = false) - see
// backend/app/services/product.py. Same effect as Resources: since
// the default list fetch is active-only, the row disappears from
// the table after invalidation.
export async function deleteProduct(id: number): Promise<void> {
  await apiClient.delete(`/api/products/${id}`)
}

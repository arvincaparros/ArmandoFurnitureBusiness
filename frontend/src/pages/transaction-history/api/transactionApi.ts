import apiClient from '../../../api/client'

import type {
  ProductSummary,
  SalesTransactionCreateRequest,
  SalesTransactionResponse,
  SalesTransactionUpdateRequest,
} from './transactionTypes'

// No query params exist on this endpoint (no filter, sort, or
// pagination support) - it always returns the full table, ordered
// transaction_date then id (backend/app/services/transaction.py::
// get_transactions). Search/sort in this module are therefore
// legitimately client-side: they operate over the complete dataset,
// never a partial page of it.
export async function fetchTransactions(): Promise<
  SalesTransactionResponse[]
> {
  const response = await apiClient.get<SalesTransactionResponse[]>(
    '/api/transactions',
  )

  return response.data
}

export async function createTransaction(
  data: SalesTransactionCreateRequest,
): Promise<SalesTransactionResponse> {
  const response = await apiClient.post<SalesTransactionResponse>(
    '/api/transactions',
    data,
  )

  return response.data
}

// product_id is never sent (SalesTransactionUpdateRequest has no such
// field) - the backend rejects reassigning a transaction to a
// different product on update.
export async function updateTransaction(
  id: number,
  data: SalesTransactionUpdateRequest,
): Promise<SalesTransactionResponse> {
  const response = await apiClient.patch<SalesTransactionResponse>(
    `/api/transactions/${id}`,
    data,
  )

  return response.data
}

// Hard delete (see app/services/transaction.py::delete_transaction) -
// unlike Resources/Products there is no is_active flag on
// SalesTransaction, so this permanently removes the row. No
// soft-delete equivalent exists in the current backend contract.
export async function deleteTransaction(
  id: number,
): Promise<void> {
  await apiClient.delete(`/api/transactions/${id}`)
}

// Default (include_inactive=false) - a transaction cannot be created
// against an inactive product (backend/app/services/transaction.py::
// create_transaction rejects it with 400), so the create-form picker
// must only ever offer active products.
export async function fetchProductSummaries(): Promise<
  ProductSummary[]
> {
  const response = await apiClient.get<ProductSummary[]>(
    '/api/products',
  )

  return response.data
}

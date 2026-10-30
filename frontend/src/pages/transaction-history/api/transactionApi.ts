import apiClient from '../../../api/client'

import type {
  ProductSummary,
  SalesTransactionCreateRequest,
  SalesTransactionListResponse,
  SalesTransactionResponse,
  SalesTransactionUpdateRequest,
} from './transactionTypes'

import {
  DEFAULT_TRANSACTION_FILTER,
  type TransactionFilter,
} from '../types'

// Maps the UI filter onto the endpoint's three mutually exclusive
// modes. Sending no params is NOT "give me everything" - the backend
// resolves the 7 most recent distinct transaction DATES from the
// stored data, so the default view is anchored to the newest row
// rather than to this browser's clock. 'all' has to say so
// explicitly with show_all=true.
export function toTransactionQueryParams(
  filter: TransactionFilter,
): Record<string, string> {
  if (filter.mode === 'all') {
    return { show_all: 'true' }
  }

  if (filter.mode === 'custom') {
    const params: Record<string, string> = {}

    // Omitted entirely rather than sent as empty strings: FastAPI
    // rejects "" as a date with a 422, and a one-sided range (only a
    // start, or only an end) is a legitimate request.
    if (filter.startDate) {
      params.start_date = filter.startDate
    }

    if (filter.endDate) {
      params.end_date = filter.endDate
    }

    return params
  }

  return {}
}

// Ordering is still transaction_date then id, server-side
// (backend/app/services/transaction.py::get_transactions). Search and
// sort in this module remain client-side, but they now operate over
// the server-resolved window instead of the entire table - which is
// the point of the change: the default view no longer downloads all
// history to show the recent part of it.
export async function fetchTransactions(
  filter: TransactionFilter = DEFAULT_TRANSACTION_FILTER,
): Promise<SalesTransactionListResponse> {
  const response = await apiClient.get<SalesTransactionListResponse>(
    '/api/transactions',
    { params: toTransactionQueryParams(filter) },
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

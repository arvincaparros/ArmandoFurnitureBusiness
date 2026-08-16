import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import {
  createTransaction,
  deleteTransaction,
  fetchProductSummaries,
  fetchTransactions,
  updateTransaction,
} from '../api/transactionApi'

import { toUiTransactions } from '../api/transactionAdapter'

import type {
  SalesTransactionCreateRequest,
  SalesTransactionUpdateRequest,
} from '../api/transactionTypes'

const TRANSACTIONS_QUERY_KEY = ['transactions']
const TRANSACTION_PRODUCTS_QUERY_KEY = [
  'transactions',
  'products',
]

// Every transaction mutation (create/update/delete) changes the
// monthly historical demand Demand Forecasting computes live from
// sales_transactions on every GET /api/forecast and GET
// /api/forecast/timeseries call - see app/services/forecasting.py::
// get_monthly_historical_demand. Both are separate query keys this
// module doesn't otherwise know about ('forecast', owned by
// useForecast.ts; 'forecast-timeseries' is per-product-scoped, so
// only the affected product's own entry is invalidated, not the
// whole family). ['dashboard-summary'] is deliberately NOT
// invalidated here - its total_sales/total_sales_profit fields are
// real but are never read by dashboardAdapter.ts, so there's nothing
// currently displayed that would go stale.
const invalidateForecastQueries = (
  queryClient: ReturnType<typeof useQueryClient>,
  productId: number,
) => {
  queryClient.invalidateQueries({ queryKey: ['forecast'] })
  queryClient.invalidateQueries({
    queryKey: ['forecast-timeseries', productId],
  })
}

const useTransactions = () => {
  const queryClient = useQueryClient()

  const transactionsQuery = useQuery({
    queryKey: TRANSACTIONS_QUERY_KEY,
    queryFn: fetchTransactions,
  })

  const productsQuery = useQuery({
    queryKey: TRANSACTION_PRODUCTS_QUERY_KEY,
    queryFn: fetchProductSummaries,
  })

  const invalidateTransactions = () =>
    queryClient.invalidateQueries({
      queryKey: TRANSACTIONS_QUERY_KEY,
    })

  const createMutation = useMutation({
    mutationFn: (data: SalesTransactionCreateRequest) =>
      createTransaction(data),
    onSuccess: (created) => {
      invalidateTransactions()
      invalidateForecastQueries(
        queryClient,
        created.product_id,
      )
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number
      data: SalesTransactionUpdateRequest
    }) => updateTransaction(id, data),
    onSuccess: (updated) => {
      invalidateTransactions()
      // product_id comes from the update response, not the request
      // (SalesTransactionUpdateRequest never carries one) - it's
      // always the transaction's real, unchanged product.
      invalidateForecastQueries(
        queryClient,
        updated.product_id,
      )
    },
  })

  // DELETE /api/transactions/{id} returns no body, so product_id
  // can't come from the response - the caller supplies it from the
  // transaction being deleted (it already has it).
  const deleteMutation = useMutation({
    mutationFn: ({ id }: { id: number; productId: number }) =>
      deleteTransaction(id),
    onSuccess: (_data, variables) => {
      invalidateTransactions()
      invalidateForecastQueries(
        queryClient,
        variables.productId,
      )
    },
  })

  return {
    transactions: toUiTransactions(
      transactionsQuery.data ?? [],
      productsQuery.data ?? [],
    ),
    isLoading:
      transactionsQuery.isLoading ||
      productsQuery.isLoading,
    isError:
      transactionsQuery.isError || productsQuery.isError,

    products: productsQuery.data ?? [],

    createTransaction: createMutation.mutateAsync,
    isCreating: createMutation.isPending,

    updateTransaction: updateMutation.mutateAsync,
    isUpdating: updateMutation.isPending,

    deleteTransaction: deleteMutation.mutateAsync,
    isDeleting: deleteMutation.isPending,
  }
}

export default useTransactions

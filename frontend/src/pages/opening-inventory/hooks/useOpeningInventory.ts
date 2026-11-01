import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import {
  createOpeningInventorySet,
  fetchOpeningInventorySets,
  fetchOpeningInventoryStatus,
  reviewOpeningInventorySet,
  updateOpeningInventorySet,
} from '../api/openingInventoryApi'

import { fetchProductSummaries } from '../../transaction-history/api/transactionApi'

import type {
  OpeningInventorySetCreateRequest,
  OpeningInventorySetUpdateRequest,
} from '../api/openingInventoryTypes'

const OPENING_INVENTORY_KEY = ['opening-inventory']
const OPENING_INVENTORY_STATUS_KEY = [
  'opening-inventory',
  'status',
]

const useOpeningInventory = () => {
  const queryClient = useQueryClient()

  const setsQuery = useQuery({
    queryKey: OPENING_INVENTORY_KEY,
    queryFn: fetchOpeningInventorySets,
  })

  const statusQuery = useQuery({
    queryKey: OPENING_INVENTORY_STATUS_KEY,
    queryFn: fetchOpeningInventoryStatus,
  })

  const productsQuery = useQuery({
    queryKey: ['opening-inventory', 'products'],
    queryFn: fetchProductSummaries,
  })

  // Reviewing a set switches stock validation on, which changes what
  // EVERY stock-aware screen must show and enforce - so the inventory
  // overview and the transaction list both go stale here, not just
  // this page's own queries. Without this, Transaction History keeps
  // serving its cached unvalidated view for the full 5-minute global
  // staleTime (see app/providers.tsx, refetchOnWindowFocus off).
  const invalidateEverythingStockAware = () => {
    queryClient.invalidateQueries({
      queryKey: OPENING_INVENTORY_KEY,
    })
    queryClient.invalidateQueries({ queryKey: ['inventory'] })
    queryClient.invalidateQueries({ queryKey: ['transactions'] })
  }

  const createMutation = useMutation({
    mutationFn: (data: OpeningInventorySetCreateRequest) =>
      createOpeningInventorySet(data),
    onSuccess: invalidateEverythingStockAware,
  })

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number
      data: OpeningInventorySetUpdateRequest
    }) => updateOpeningInventorySet(id, data),
    onSuccess: invalidateEverythingStockAware,
  })

  const reviewMutation = useMutation({
    mutationFn: (id: number) => reviewOpeningInventorySet(id),
    onSuccess: invalidateEverythingStockAware,
  })

  return {
    sets: setsQuery.data ?? [],
    status: statusQuery.data ?? null,
    draftSet: statusQuery.data?.draft_set ?? null,
    reviewedSet: statusQuery.data?.reviewed_set ?? null,
    isStockValidationEnabled:
      statusQuery.data?.stock_validation_enabled ?? false,
    products: productsQuery.data ?? [],

    isLoading:
      setsQuery.isLoading ||
      statusQuery.isLoading ||
      productsQuery.isLoading,
    isError:
      setsQuery.isError ||
      statusQuery.isError ||
      productsQuery.isError,

    createDraft: createMutation.mutateAsync,
    updateDraft: updateMutation.mutateAsync,
    isSaving:
      createMutation.isPending || updateMutation.isPending,

    reviewSet: reviewMutation.mutateAsync,
    isReviewing: reviewMutation.isPending,
  }
}

export default useOpeningInventory

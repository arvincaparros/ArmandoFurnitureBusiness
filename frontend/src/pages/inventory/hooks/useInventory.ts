import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import { fetchInventory } from '../api/inventoryApi'
import { toUiInventory } from '../api/inventoryAdapter'

// The canonical inventory query key. Tasks that change stock -
// applying production, saving/reviewing opening inventory, and every
// transaction mutation - all invalidate exactly this key, so they do
// not need to know anything else about this module.
export const INVENTORY_QUERY_KEY = ['inventory']

const useInventory = () => {
  const inventoryQuery = useQuery({
    queryKey: INVENTORY_QUERY_KEY,
    queryFn: fetchInventory,
  })

  const inventory = useMemo(
    () =>
      inventoryQuery.data
        ? toUiInventory(inventoryQuery.data)
        : null,
    [inventoryQuery.data],
  )

  return {
    inventory,
    products: inventory?.products ?? [],
    cycleId: inventory?.cycleId ?? null,
    cycleStartDate: inventory?.cycleStartDate ?? null,
    cycleEndDate: inventory?.cycleEndDate ?? null,
    isStockValidationEnabled:
      inventory?.stockValidationEnabled ?? false,

    isLoading: inventoryQuery.isLoading,
    isError: inventoryQuery.isError,
  }
}

export default useInventory

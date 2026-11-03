import apiClient from '../../../api/client'

import type { InventoryOverviewResponse } from './inventoryTypes'

export async function fetchInventory(): Promise<
  InventoryOverviewResponse
> {
  const response = await apiClient.get<InventoryOverviewResponse>(
    '/api/inventory',
  )

  return response.data
}

import apiClient from '../../../api/client'

// GET /api/production-cycles/{cycleId}/allocations - the actual
// committed production plan (backend/app/schemas/allocation.py).
// Local, minimal duplicate of production-allocation/api/
// productionApi.ts's fetchProductionAllocations - same convention
// already used elsewhere in this app (Dashboard/Production keep
// their own local copies of cross-module fetches, e.g.
// fetchProductSummaries). Used here only to tell whether ANY
// allocation has been applied for the cycle yet, for the "no
// production allocation applied yet" empty state - Resource
// Utilization's own consumed/remaining/utilization numbers still
// come entirely from GET /api/resource-utilization/{cycleId}, this
// is not a second source of consumption data.
export interface ProductionAllocationResponse {
  id: number
  production_cycle_id: number
  product_id: number
  quantity: string
}

export async function fetchProductionAllocations(
  cycleId: number,
): Promise<ProductionAllocationResponse[]> {
  const response = await apiClient.get<
    ProductionAllocationResponse[]
  >(`/api/production-cycles/${cycleId}/allocations`)

  return response.data
}

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

// GET /api/production-cycles/{cycle_id}/feasibility - local, minimal
// duplicate of production-allocation/api/productionApi.ts's
// ProductionFeasibilityResponse/fetchFeasibility, same convention as
// ProductionAllocationResponse/fetchProductionAllocations above. Used
// here only to tell whether the last APPLIED allocation still fits
// current resource capacity, never the Adaptive Optimization preview
// (that preview is never persisted and has no applied_at).
export interface ResourceFeasibilityBottleneck {
  resource_id: number
  resource_name: string
  unit: string
  shortage_quantity: string
}

export interface ProductionFeasibilityResponse {
  cycle_id: number
  is_feasible: boolean
  bottlenecks: ResourceFeasibilityBottleneck[]
  needs_reoptimization: boolean
  applied_at: string | null
}

export async function fetchFeasibility(
  cycleId: number,
): Promise<ProductionFeasibilityResponse> {
  const response = await apiClient.get<ProductionFeasibilityResponse>(
    `/api/production-cycles/${cycleId}/feasibility`,
  )

  return response.data
}

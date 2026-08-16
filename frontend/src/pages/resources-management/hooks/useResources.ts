import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import {
  createResource,
  deleteResource,
  fetchResources,
  updateResource,
} from '../api/resourceApi'

import {
  createCycleResource,
  fetchCycleResources,
  updateCycleResource,
} from '../api/cycleResourceApi'

import { toUiResources } from '../api/resourceAdapter'

import useLatestProductionCycle from '../../../hooks/useLatestProductionCycle'

import type {
  ResourceCreateRequest,
  ResourceUpdateRequest,
} from '../api/resourceTypes'
import type { CycleResourceResponse } from '../api/cycleResourceTypes'

const RESOURCES_QUERY_KEY = ['resources']

const useResources = () => {
  const queryClient = useQueryClient()

  const resourcesQuery = useQuery({
    queryKey: RESOURCES_QUERY_KEY,
    queryFn: fetchResources,
  })

  // Canonical "latest production cycle" resolution (created_at DESC,
  // id DESC), shared with Production Allocation and Resource
  // Utilization - see the Production Cycle Selection Consistency
  // Audit. Availability/price (CycleResource) are scoped to this
  // cycle, so it's the source this page reads and writes them
  // against.
  const {
    cycleId: latestCycleId,
    hasCycle,
  } = useLatestProductionCycle()

  // Same ['cycle-resources', cycleId] query key as
  // product-data-management/hooks/useProducts.ts - shared verbatim so
  // a pricing edit made here invalidates that module's cost
  // calculation too, matching the 'resources-all' sharing convention
  // already used elsewhere in this app.
  const cycleResourcesQuery = useQuery({
    queryKey: ['cycle-resources', latestCycleId],
    queryFn: () => fetchCycleResources(latestCycleId!),
    enabled: latestCycleId !== null,
  })

  const cycleResourcesByResourceId = new Map<
    number,
    CycleResourceResponse
  >(
    (cycleResourcesQuery.data ?? []).map((cycleResource) => [
      cycleResource.resource_id,
      cycleResource,
    ]),
  )

  const invalidateResources = () =>
    queryClient.invalidateQueries({
      queryKey: RESOURCES_QUERY_KEY,
    })

  const invalidateCycleResources = () => {
    queryClient.invalidateQueries({
      queryKey: ['cycle-resources', latestCycleId],
    })

    // Resource Utilization (resource-utilization-report/hooks/
    // useResourceUtilization.ts) computes its utilization rates live
    // from these same CycleResource rows for this cycle - goes stale
    // the same way Products/Dashboard already do on each other's
    // mutations elsewhere in this app.
    queryClient.invalidateQueries({
      queryKey: ['resource-utilization', latestCycleId],
    })
  }

  // Create/update/delete all change the shared resource catalog that
  // Product Resource Requirements (useProductResourceRequirements.ts)
  // and the Products table (useProducts.ts) both read via
  // fetchAllResourcesForPicker() - GET /api/resources?include_inactive=true,
  // a different request/query key ('resources-all') from this page's
  // own active-only ['resources'] list, and one this module doesn't
  // otherwise know about. Invalidating it here lets whichever of
  // those re-fetch normally next time it's mounted - no second
  // resources API call is made from this module.
  const invalidateResourcesCatalog = () =>
    queryClient.invalidateQueries({
      queryKey: ['resources-all'],
    })

  const createMutation = useMutation({
    mutationFn: (data: ResourceCreateRequest) =>
      createResource(data),
    onSuccess: () => {
      invalidateResources()
      invalidateResourcesCatalog()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number
      data: ResourceUpdateRequest
    }) => updateResource(id, data),
    onSuccess: () => {
      invalidateResources()
      invalidateResourcesCatalog()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteResource(id),
    onSuccess: () => {
      invalidateResources()
      invalidateResourcesCatalog()
    },
  })

  // Availability/price live on CycleResource, not the global Resource
  // record (see cycleResourceApi.ts), so saving them is a second,
  // separate write against the latest production cycle - update if a
  // CycleResource row already exists for this resource in that cycle,
  // otherwise create one. Throws if no production cycle exists yet
  // (the modal disables these fields in that case, so this is a
  // genuine precondition, not a user-facing validation message).
  const pricingMutation = useMutation({
    mutationFn: ({
      resourceId,
      data,
    }: {
      resourceId: number
      data: { available_quantity: number; unit_price: number }
    }) => {
      if (latestCycleId === null) {
        throw new Error(
          'No production cycle exists yet - availability and unit price cannot be saved.',
        )
      }

      const existing = cycleResourcesByResourceId.get(resourceId)

      if (existing) {
        return updateCycleResource(
          latestCycleId,
          resourceId,
          data,
        )
      }

      return createCycleResource(latestCycleId, {
        resource_id: resourceId,
        ...data,
      })
    },
    onSuccess: () => {
      invalidateCycleResources()
    },
  })

  return {
    resources: toUiResources(
      resourcesQuery.data ?? [],
      cycleResourcesByResourceId,
    ),
    isLoading:
      resourcesQuery.isLoading || cycleResourcesQuery.isLoading,
    isError: resourcesQuery.isError,

    hasCycle,

    createResource: createMutation.mutateAsync,
    isCreating: createMutation.isPending,

    updateResource: updateMutation.mutateAsync,
    isUpdating: updateMutation.isPending,

    deleteResource: deleteMutation.mutateAsync,
    isDeleting: deleteMutation.isPending,

    savePricing: pricingMutation.mutateAsync,
    isSavingPricing: pricingMutation.isPending,
  }
}

export default useResources

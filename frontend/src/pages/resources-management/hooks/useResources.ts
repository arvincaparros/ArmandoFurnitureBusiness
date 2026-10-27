import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import {
  createResource,
  deleteResource,
  fetchAllResourcesIncludingInactive,
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

  // Every resource in the database, active and inactive - powers the
  // Name select in the Add Resource form (AddResourceModal.tsx).
  // Deliberately the same ['resources-all'] query already invalidated
  // by every mutation below, so a create/update/delete here keeps
  // this list correct without a second, separate invalidation call.
  // It is also the query Product Resource Requirements already reads
  // (fetchAllResourcesForPicker), so it introduces no new request.
  const allResourcesQuery = useQuery({
    queryKey: ['resources-all'],
    queryFn: fetchAllResourcesIncludingInactive,
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

  // Production Allocation's "Needs Re-optimization" banner
  // (useProductionAllocation.ts's feasibilityQueryKey) is derived from
  // this cycle's CycleResource rows AND from the underlying Resource
  // catalog (e.g. deactivating a resource via delete) - so this is
  // called both from invalidateCycleResources below (the pricing
  // write path) and directly from the catalog mutations' onSuccess
  // callbacks, not just nested inside invalidateCycleResources.
  const invalidateFeasibility = () =>
    queryClient.invalidateQueries({
      queryKey: ['feasibility', latestCycleId],
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

    invalidateFeasibility()
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
      invalidateFeasibility()
    },
  })

  // The only write path that inserts a global Resource row - used by
  // the Add Resource form's "Create New" mode
  // (AddResourceModal.tsx). Selecting an existing resource never
  // reaches this: that flow writes CycleResource only, so an
  // existing resource keeps its own id and is never duplicated.
  // Invalidating 'resources-all' is what makes the new row show up
  // in the selector (and in Product Resource Requirements) without a
  // reload.
  const createMutation = useMutation({
    mutationFn: (data: ResourceCreateRequest) =>
      createResource(data),
    onSuccess: () => {
      invalidateResources()
      invalidateResourcesCatalog()
      invalidateFeasibility()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteResource(id),
    onSuccess: () => {
      invalidateResources()
      invalidateResourcesCatalog()
      invalidateFeasibility()
    },
  })

  // Reactivation is a PATCH of is_active on the existing Resource row
  // - the same endpoint the delete flow soft-deletes with. It never
  // creates a row, rewrites category/unit, or touches CycleResource
  // quantities/prices. Feasibility and Resource Utilization both
  // filter the catalog by is_active, so they go stale when a resource
  // comes back.
  const reactivateMutation = useMutation({
    mutationFn: (id: number) =>
      updateResource(id, { is_active: true }),
    onSuccess: () => {
      invalidateResources()
      invalidateResourcesCatalog()
      invalidateFeasibility()

      queryClient.invalidateQueries({
        queryKey: ['resource-utilization', latestCycleId],
      })
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

  const uiResources = toUiResources(
    resourcesQuery.data ?? [],
    cycleResourcesByResourceId,
  )

  // Active and inactive catalog rows with the latest cycle's
  // availability/price resolved by resource id. Inactive resources
  // keep their CycleResource row after a soft delete (see
  // delete_resource), so their real values are shown rather than
  // fabricated nulls - and reactivation never has to touch them.
  const allUiResources = toUiResources(
    allResourcesQuery.data ?? [],
    cycleResourcesByResourceId,
  )

  const inactiveResources = allUiResources.filter(
    (resource) => !resource.isActive,
  )

  return {
    resources: uiResources,
    inactiveResources,
    selectableResources: allUiResources,
    isExistingResourcesLoading: allResourcesQuery.isLoading,
    isExistingResourcesError: allResourcesQuery.isError,
    isLoading:
      resourcesQuery.isLoading || cycleResourcesQuery.isLoading,
    isError: resourcesQuery.isError,

    hasCycle,

    updateResource: updateMutation.mutateAsync,
    isUpdating: updateMutation.isPending,

    createResource: createMutation.mutateAsync,
    isCreating: createMutation.isPending,

    deleteResource: deleteMutation.mutateAsync,
    isDeleting: deleteMutation.isPending,

    reactivateResource: reactivateMutation.mutateAsync,
    isReactivating: reactivateMutation.isPending,

    savePricing: pricingMutation.mutateAsync,
    isSavingPricing: pricingMutation.isPending,
  }
}

export default useResources

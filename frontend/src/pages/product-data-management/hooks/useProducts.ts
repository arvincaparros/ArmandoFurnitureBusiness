import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import {
  createProduct,
  deleteProduct,
  fetchProducts,
  updateProduct,
} from '../api/productApi'

import {
  fetchAllResourcesForPicker,
  fetchProductResourceRequirements,
} from '../api/productResourceApi'

import { fetchCycleResources } from '../api/cycleResourceApi'

import {
  resolveRequirements,
  type ResolvedRequirement,
} from '../api/productResourceAdapter'

import {
  buildResourceCostRates,
  toUiProducts,
} from '../api/productAdapter'

import useLatestProductionCycle from '../../../hooks/useLatestProductionCycle'

import type {
  ProductCreateRequest,
  ProductUpdateRequest,
} from '../api/productTypes'

const PRODUCTS_QUERY_KEY = ['products']

const useProducts = () => {
  const queryClient = useQueryClient()

  const productsQuery = useQuery({
    queryKey: PRODUCTS_QUERY_KEY,
    queryFn: fetchProducts,
  })

  const products = productsQuery.data ?? []

  // Same resource catalog GET /api/resources?include_inactive=true
  // and the same 'resources-all' query key already used by the Edit
  // Product modal's useProductResourceRequirements.ts - one shared
  // cache entry, not a second fetch of the same data.
  const resourcesQuery = useQuery({
    queryKey: ['resources-all'],
    queryFn: fetchAllResourcesForPicker,
  })

  // One request per product for GET /api/products/{id}/resources -
  // the backend only supports per-product retrieval (no batch
  // endpoint exists, and this phase doesn't add one), so this is the
  // smallest correct way to get every row's requirements. Each uses
  // the exact same ['product-resources', productId] query key as
  // useProductResourceRequirements.ts, so React Query caches and
  // dedupes them automatically - opening the Edit modal for a product
  // reuses whatever the table already fetched, and vice versa. Fired
  // in parallel via useQueries (not sequentially in a loop), and
  // only once each thanks to query-key-based caching - no polling,
  // no repeated refetching on every render.
  const requirementsQueries = useQueries({
    queries: products.map((product) => ({
      queryKey: ['product-resources', product.id],
      queryFn: () =>
        fetchProductResourceRequirements(product.id),
    })),
  })

  const resources = resourcesQuery.data ?? []

  // Same catalog as `resources` above (['resources-all'], no second
  // query) - just the active subset, which is what determines which
  // resource columns the Products table renders at all. Deactivating
  // a resource removes it from here, so its column disappears next
  // time this list is fetched fresh.
  const activeResources = resources.filter(
    (resource) => resource.is_active,
  )

  // Canonical "latest production cycle" resolution (created_at DESC,
  // id DESC), shared with Production Allocation and Resource
  // Utilization - see the Production Cycle Selection Consistency
  // Audit. Resource unit prices (CycleResource) are scoped to this
  // cycle, so it's the source cost auto-calculation reads from.
  const {
    cycleId: latestCycleId,
    isLoading: isCycleLoading,
  } = useLatestProductionCycle()

  // Same ['cycle-resources', cycleId] query key as
  // resources-management/hooks/useResources.ts - a pricing edit made
  // there invalidates this query too, so cost columns here go stale
  // and refetch correctly without a second, module-specific
  // invalidation call.
  const cycleResourcesQuery = useQuery({
    queryKey: ['cycle-resources', latestCycleId],
    queryFn: () => fetchCycleResources(latestCycleId!),
    enabled: latestCycleId !== null,
  })

  const costRates = buildResourceCostRates(
    activeResources,
    cycleResourcesQuery.data ?? [],
  )

  const activeResourceIds = activeResources.map(
    (resource) => resource.id,
  )

  const requirementsByProductId = new Map<
    number,
    ResolvedRequirement[]
  >(
    products.map((product, index) => [
      product.id,
      resolveRequirements(
        requirementsQueries[index]?.data ?? [],
        resources,
      ),
    ]),
  )

  // A per-product requirements fetch failing degrades that one
  // product's resource columns to "-" (no data resolved) rather than
  // failing the whole table - handled naturally above since a failed
  // query's .data is undefined, treated the same as "not loaded yet".
  const isRequirementsLoading = requirementsQueries.some(
    (query) => query.isLoading,
  )

  const invalidateProducts = () =>
    queryClient.invalidateQueries({
      queryKey: PRODUCTS_QUERY_KEY,
    })

  // Create/update/delete all change total_products on the Dashboard
  // summary (backend/app/services/dashboard.py::get_dashboard_summary)
  // - that's a separate query key ('dashboard-summary', owned by
  // useDashboard.ts) this module doesn't otherwise know about.
  // Invalidating the whole summary query here (rather than reaching
  // into Dashboard's cache value to patch one field) lets it
  // recompute normally next time it's fetched - no second dashboard
  // API call is made from this module.
  const invalidateDashboardSummary = () =>
    queryClient.invalidateQueries({
      queryKey: ['dashboard-summary'],
    })

  const createMutation = useMutation({
    mutationFn: (data: ProductCreateRequest) =>
      createProduct(data),
    onSuccess: () => {
      invalidateProducts()
      invalidateDashboardSummary()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number
      data: ProductUpdateRequest
    }) => updateProduct(id, data),
    onSuccess: () => {
      invalidateProducts()
      invalidateDashboardSummary()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteProduct(id),
    onSuccess: () => {
      invalidateProducts()
      invalidateDashboardSummary()
    },
  })

  return {
    products: toUiProducts(
      products,
      requirementsByProductId,
      activeResourceIds,
      costRates,
    ),
    activeResources,
    // Resource columns wait on the resource catalog + per-product
    // requirement fetches too, so rows don't render with a
    // premature/incomplete set of dashes before those resolve.
    // Requirement-query errors are intentionally excluded from
    // isError (see the comment above requirementsQueries) - a failed
    // per-product fetch degrades that row's resource columns, it
    // doesn't fail the whole table. Cost columns similarly wait on
    // cycle-resource pricing so they don't briefly flash "unpriced"
    // before that query resolves; a failed/absent cycle just leaves
    // costs null (handled by calculateCosts), it doesn't fail the
    // table either.
    isLoading:
      productsQuery.isLoading ||
      resourcesQuery.isLoading ||
      isRequirementsLoading ||
      isCycleLoading ||
      cycleResourcesQuery.isLoading,
    isError: productsQuery.isError,

    createProduct: createMutation.mutateAsync,
    isCreating: createMutation.isPending,

    updateProduct: updateMutation.mutateAsync,
    isUpdating: updateMutation.isPending,

    deleteProduct: deleteMutation.mutateAsync,
    isDeleting: deleteMutation.isPending,
  }
}

export default useProducts

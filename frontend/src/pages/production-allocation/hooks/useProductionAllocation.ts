import { useMemo, useState } from 'react'

import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import {
  applyOptimization,
  fetchOptimizationHistory,
  fetchProductionAllocations,
  fetchProductSummaries,
  runOptimization,
} from '../api/productionApi'

import {
  findLatestOptimalRun,
  fromAllocations,
  fromHistoryRun,
  fromOptimizeResponse,
} from '../api/productionAdapter'

import useLatestProductionCycle from '../../../hooks/useLatestProductionCycle'

import type {
  OptimizationSummary,
  ProductionPlan,
} from '../types'

const useProductionAllocation = () => {
  const queryClient = useQueryClient()

  // Canonical resolution (created_at DESC, id DESC), shared with
  // Resource Utilization so both pages always agree on which cycle
  // is current - see the Production Cycle Selection Consistency
  // Audit. No longer fetches the whole cycle list itself.
  const {
    cycleId: latestCycleId,
    hasCycle,
    isLoading: isCycleLoading,
    isError: isCycleError,
  } = useLatestProductionCycle()

  const historyQueryKey = [
    'optimization-history',
    latestCycleId,
  ]

  const historyQuery = useQuery({
    queryKey: historyQueryKey,
    queryFn: () => fetchOptimizationHistory(latestCycleId!),
    enabled: latestCycleId !== null,
  })

  const productsQuery = useQuery({
    queryKey: ['products'],
    queryFn: fetchProductSummaries,
  })

  // The ACTUAL committed allocation for the cycle - distinct from
  // the optimization preview/history above. Only ever written by
  // POST /optimize/apply or direct manual CRUD (verified in
  // app/services/optimization.py), neither of which any current UI
  // action calls - so this is deliberately NOT invalidated by the
  // optimize mutation below (see its onSuccess: generating a new
  // preview does not change what's actually allocated).
  const allocationsQueryKey = [
    'production-allocations',
    latestCycleId,
  ]

  const allocationsQuery = useQuery({
    queryKey: allocationsQueryKey,
    queryFn: () => fetchProductionAllocations(latestCycleId!),
    enabled: latestCycleId !== null,
  })

  const currentAllocation = useMemo(
    () =>
      fromAllocations(
        allocationsQuery.data ?? [],
        productsQuery.data,
      ),
    [allocationsQuery.data, productsQuery.data],
  )

  // Holds the result of the most recent successful "Generate" click
  // in this session, so the page reflects it immediately rather
  // than waiting on the background history refetch.
  const [freshResult, setFreshResult] = useState<{
    plans: ProductionPlan[]
    summary: OptimizationSummary
  } | null>(null)

  const optimizeMutation = useMutation({
    mutationFn: async () => {
      if (latestCycleId === null) {
        throw new Error('No production cycle exists yet.')
      }

      const startedAt = new Date()
      const data = await runOptimization(latestCycleId)
      const completedAt = new Date()

      return fromOptimizeResponse(data, {
        startedAt,
        completedAt,
      })
    },
    onSuccess: (result) => {
      setFreshResult(result)

      queryClient.invalidateQueries({
        queryKey: historyQueryKey,
      })

      // The Optimization History page reads GET /api/optimization/
      // history unscoped (optimization-history/api/
      // optimizationHistoryApi.ts), under its own query key
      // ['optimization-history-page'] - a run generated here is
      // included in that same unscoped list, so it goes stale too
      // and needs invalidating alongside this page's own cycle-scoped
      // key. Apply's mutation deliberately does NOT invalidate this
      // (see applyMutation below) - apply_optimization() only reads
      // the existing latest OptimizationRun, it never creates one, so
      // there's nothing there for Optimization History to go stale
      // over.
      queryClient.invalidateQueries({
        queryKey: ['optimization-history-page'],
      })
    },
  })

  const latestOptimalRun = useMemo(
    () => findLatestOptimalRun(historyQuery.data),
    [historyQuery.data],
  )

  const persistedResult = useMemo(() => {
    if (!latestOptimalRun) {
      return null
    }

    return fromHistoryRun(latestOptimalRun, productsQuery.data)
  }, [latestOptimalRun, productsQuery.data])

  const result = freshResult ?? persistedResult

  // Apply always commits whatever the backend currently resolves as
  // "the latest OPTIMAL run" (get_latest_optimization_history_run,
  // server-side) - reusing latestOptimalRun (the same resolution
  // already driving the displayed preview) rather than a second,
  // independent check, per the approved design.
  //
  // Deliberately does NOT invalidate ['optimization-history-page'] or
  // historyQueryKey: confirmed via app/services/optimization.py::
  // apply_optimization() that it only reads the existing latest
  // OptimizationRun to build ProductionAllocation rows - it never
  // creates/modifies an OptimizationRun, so neither Optimization
  // History page ever goes stale from an Apply.
  //
  // A successful Apply DOES atomically create a new resource
  // utilization snapshot (same apply_optimization() call - see
  // save_resource_utilization_history), so both the current Resource
  // Utilization report (['resource-utilization', cycleId], read by
  // resource-utilization-report/hooks/useResourceUtilization.ts) and
  // Resource Utilization History (['resource-utilization-history'],
  // read by resource-utilization-history/hooks/
  // useResourceUtilizationHistory.ts) go stale here too - previously
  // neither was invalidated, so the new snapshot only appeared after
  // a manual refresh.
  const applyMutation = useMutation({
    mutationFn: () => {
      if (latestCycleId === null) {
        throw new Error('No production cycle exists yet.')
      }

      return applyOptimization(latestCycleId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: allocationsQueryKey,
      })

      queryClient.invalidateQueries({
        queryKey: ['resource-utilization', latestCycleId],
      })

      queryClient.invalidateQueries({
        queryKey: ['resource-utilization-history'],
      })
    },
  })

  return {
    plans: result?.plans ?? [],
    summary: result?.summary ?? null,

    hasCycle,

    isLoading:
      isCycleLoading ||
      historyQuery.isLoading ||
      productsQuery.isLoading,
    isError:
      isCycleError ||
      historyQuery.isError ||
      productsQuery.isError,

    generatePlan: () => optimizeMutation.mutateAsync(),
    isGenerating: optimizeMutation.isPending,
    generateError: optimizeMutation.error,

    currentAllocation,
    isAllocationLoading:
      allocationsQuery.isLoading || productsQuery.isLoading,
    isAllocationError:
      allocationsQuery.isError || productsQuery.isError,

    canApply: latestOptimalRun !== null,
    applyToProduction: () => applyMutation.mutateAsync(),
    isApplying: applyMutation.isPending,
    applyError: applyMutation.error,
  }
}

export default useProductionAllocation

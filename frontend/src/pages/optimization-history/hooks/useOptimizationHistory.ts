import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import {
  fetchOptimizationHistory,
  runOptimization,
} from '../api/optimizationHistoryApi'

import {
  toUiOptimizationHistory,
  toUiProfitTrend,
} from '../api/optimizationHistoryAdapter'

import useLatestProductionCycle from '../../../hooks/useLatestProductionCycle'

// Distinct query key from Production Allocation's ['optimization-history',
// cycleId] (production-allocation/hooks/useProductionAllocation.ts) -
// that one is cycle-scoped, this one deliberately isn't (see
// optimizationHistoryApi.ts), so they must never share a cache entry.
const HISTORY_QUERY_KEY = ['optimization-history-page']

const useOptimizationHistory = () => {
  const queryClient = useQueryClient()

  // Canonical resolution (created_at DESC, id DESC), the same shared
  // hook Production Allocation/Resource Utilization/Dashboard use -
  // not re-derived here. "Run Manual Optimization" always targets
  // whichever cycle those pages agree is current.
  const {
    cycleId,
    hasCycle,
    isLoading: isCycleLoading,
    isError: isCycleError,
  } = useLatestProductionCycle()

  const historyQuery = useQuery({
    queryKey: HISTORY_QUERY_KEY,
    queryFn: fetchOptimizationHistory,
  })

  const runMutation = useMutation({
    mutationFn: () => {
      if (cycleId === null) {
        throw new Error(
          'No production cycle exists yet.',
        )
      }

      return runOptimization(cycleId)
    },
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: HISTORY_QUERY_KEY,
      }),
  })

  return {
    optimizationHistory: toUiOptimizationHistory(
      historyQuery.data ?? [],
    ),
    profitTrendData: toUiProfitTrend(
      historyQuery.data ?? [],
    ),

    isLoading: historyQuery.isLoading,
    isError: historyQuery.isError,

    hasCycle,
    isCycleLoading,
    isCycleError,

    runOptimization: runMutation.mutateAsync,
    isRunning: runMutation.isPending,
    runError: runMutation.error,
  }
}

export default useOptimizationHistory

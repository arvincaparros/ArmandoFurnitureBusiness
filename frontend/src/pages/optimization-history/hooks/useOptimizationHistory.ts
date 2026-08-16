import { useQuery } from '@tanstack/react-query'

import { fetchOptimizationHistory } from '../api/optimizationHistoryApi'

import {
  toUiOptimizationHistory,
  toUiProfitTrend,
} from '../api/optimizationHistoryAdapter'

// Canonical resolution (created_at DESC, id DESC), the same shared
// query key convention used across the app. This page is a pure
// historical record now - optimization runs are only ever created via
// Production Allocation's "Generate Optimal Production Plan" ->
// "Apply to Production" workflow, never from here.
const HISTORY_QUERY_KEY = ['optimization-history-page']

const useOptimizationHistory = () => {
  const historyQuery = useQuery({
    queryKey: HISTORY_QUERY_KEY,
    queryFn: fetchOptimizationHistory,
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
  }
}

export default useOptimizationHistory

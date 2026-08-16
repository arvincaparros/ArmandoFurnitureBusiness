import { useMemo } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'

import {
  fetchResourceUtilizationHistory,
  fetchResourceUtilizationHistoryDetail,
} from '../api/utilizationHistoryApi'

import { toUiHistoryRows } from '../api/utilizationHistoryAdapter'

// Unscoped across all cycles, matching Optimization History's own
// unscoped GET /api/optimization/history - distinct key namespace
// from ['resource-utilization', cycleId] used by resource-utilization-
// report's own hook for the CURRENT (non-history) report.
const HISTORY_QUERY_KEY = ['resource-utilization-history']

const useResourceUtilizationHistory = () => {
  // GET /api/resource-utilization/history only returns per-run
  // counts, not the resource-level items the client asked this page
  // to show as rows - only GET .../history/{run_id} returns items, so
  // each run's detail is fetched here rather than changing the
  // backend's summary endpoint.
  const historyQuery = useQuery({
    queryKey: HISTORY_QUERY_KEY,
    queryFn: fetchResourceUtilizationHistory,
  })

  const runIds = historyQuery.data?.map((run) => run.id) ?? []

  const detailQueries = useQueries({
    queries: runIds.map((id) => ({
      queryKey: [...HISTORY_QUERY_KEY, id],
      queryFn: () => fetchResourceUtilizationHistoryDetail(id),
    })),
  })

  const isDetailLoading = detailQueries.some(
    (query) => query.isLoading,
  )

  const isDetailError = detailQueries.some(
    (query) => query.isError,
  )

  // detailQueries preserves the same order as runIds, which in turn
  // preserves the summary list's own ordering (generated_at DESC, id
  // DESC - see get_resource_utilization_history) - no re-sort needed,
  // newest run's rows come first.
  const rows = useMemo(
    () =>
      detailQueries
        .filter((query) => query.data !== undefined)
        .flatMap((query) => toUiHistoryRows(query.data!)),
    [detailQueries],
  )

  return {
    rows,
    isLoading: historyQuery.isLoading || isDetailLoading,
    isError: historyQuery.isError || isDetailError,
  }
}

export default useResourceUtilizationHistory

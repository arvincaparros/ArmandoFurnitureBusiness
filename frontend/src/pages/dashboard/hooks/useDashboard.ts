import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'

import {
  fetchDashboardSummary,
  fetchLatestResourceUtilization,
  fetchOptimizationHistory,
  fetchProductSummaries,
} from '../api/dashboardApi'

import {
  buildDashboardRecommendations,
  buildDashboardResourceUtilization,
  buildDashboardStats,
  findLatestOptimalRun,
} from '../api/dashboardAdapter'

import useLatestProductionCycle from '../../../hooks/useLatestProductionCycle'

const useDashboard = () => {
  const summaryQuery = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: fetchDashboardSummary,
  })

  // Canonical resolution (created_at DESC, id DESC), shared with
  // Production Allocation and Resource Utilization so the
  // recommendation shown here can never come from a different cycle
  // than what those pages are operating on - see the Dashboard
  // Latest-Cycle Optimization Scoping report.
  const {
    cycleId,
    hasCycle,
    isLoading: isCycleLoading,
    isError: isCycleError,
  } = useLatestProductionCycle()

  const optimizationHistoryQuery = useQuery({
    queryKey: ['optimization-history', cycleId],
    queryFn: () => fetchOptimizationHistory(cycleId!),
    enabled: cycleId !== null,
  })

  const productsQuery = useQuery({
    queryKey: ['products'],
    queryFn: fetchProductSummaries,
  })

  const resourceUtilizationQuery = useQuery({
    queryKey: ['resource-utilization-latest'],
    queryFn: fetchLatestResourceUtilization,
  })

  // Shared by the "Expected Revenue" stat and the recommendations
  // table so both always refer to the same run - now additionally
  // guaranteed to be the latest cycle's own run, not merely the
  // globally-newest run across every cycle.
  const latestOptimalRun = useMemo(
    () => findLatestOptimalRun(optimizationHistoryQuery.data),
    [optimizationHistoryQuery.data],
  )

  const stats = useMemo(
    () =>
      buildDashboardStats(
        summaryQuery.data,
        latestOptimalRun,
        productsQuery.data,
      ),
    [summaryQuery.data, latestOptimalRun, productsQuery.data],
  )

  const recommendations = useMemo(
    () =>
      buildDashboardRecommendations(
        latestOptimalRun,
        productsQuery.data,
      ),
    [latestOptimalRun, productsQuery.data],
  )

  const resourceUtilization = useMemo(
    () =>
      buildDashboardResourceUtilization(
        resourceUtilizationQuery.data,
      ),
    [resourceUtilizationQuery.data],
  )

  // Once the cycle itself is known to not exist, there is nothing
  // to wait on for optimization history - avoids the stats row
  // staying in a loading state forever when hasCycle is false.
  const isOptimizationHistoryPending =
    isCycleLoading ||
    (hasCycle && optimizationHistoryQuery.isLoading)

  return {
    // Stat cards draw on summary + cycle resolution + optimization
    // history + products (Expected Revenue needs all of them), so
    // the row loads/errors as one unit rather than four
    // independently-timed cards.
    stats,
    isStatsLoading:
      summaryQuery.isLoading ||
      isOptimizationHistoryPending ||
      productsQuery.isLoading,
    isStatsError:
      summaryQuery.isError ||
      isCycleError ||
      optimizationHistoryQuery.isError ||
      productsQuery.isError,

    recommendations,
    isRecommendationsLoading:
      isOptimizationHistoryPending || productsQuery.isLoading,
    isRecommendationsError:
      isCycleError ||
      optimizationHistoryQuery.isError ||
      productsQuery.isError,

    resourceUtilization,
    isResourceUtilizationLoading:
      resourceUtilizationQuery.isLoading,
    isResourceUtilizationError:
      resourceUtilizationQuery.isError,
  }
}

export default useDashboard

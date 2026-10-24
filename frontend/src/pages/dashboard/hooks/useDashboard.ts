import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'

import {
  fetchDashboardSummary,
  fetchLatestResourceUtilization,
  fetchOptimizationHistory,
  fetchProductSummaries,
  fetchProductionAllocations,
} from '../api/dashboardApi'

import {
  buildDashboardRecommendations,
  buildDashboardResourceUtilization,
  buildDashboardStats,
  findLatestOptimalRun,
  summarizeAppliedAllocation,
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
    // include_hidden: a caller that must operate on the live plan
    // should never be blinded by a hidden run. The approved
    // Optimization History cleanup leaves every row visible, so this
    // has no effect today; it stays as the defensive option. Shares
    // this key with useProductionAllocation, which asks for the same
    // flag, so both pages stay on one cached copy.
    queryFn: () => fetchOptimizationHistory(cycleId!, true),
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

  // Fallback source for the financial stat cards once no usable run
  // exists (e.g. right after the approved Optimization History
  // cleanup deleted the old test runs): the committed allocation is
  // preserved independently of any run and priced by the backend
  // from current cycle data. Same query key as useProductionAllocation,
  // so both pages read one cache entry and an Apply there refreshes
  // it here. Only fetched when history resolved without a usable run,
  // so normal operation costs no extra request.
  const appliedAllocationQuery = useQuery({
    queryKey: ['production-allocations', cycleId],
    queryFn: () => fetchProductionAllocations(cycleId!),
    enabled:
      cycleId !== null &&
      optimizationHistoryQuery.isSuccess &&
      latestOptimalRun === null,
  })

  const appliedAllocation = useMemo(
    () => summarizeAppliedAllocation(appliedAllocationQuery.data),
    [appliedAllocationQuery.data],
  )

  const stats = useMemo(
    () =>
      buildDashboardStats(
        summaryQuery.data,
        latestOptimalRun,
        productsQuery.data,
        appliedAllocation,
      ),
    [
      summaryQuery.data,
      latestOptimalRun,
      productsQuery.data,
      appliedAllocation,
    ],
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
    // history + products (Expected Revenue needs all of them, and
    // the committed-allocation fallback adds one more query), so
    // the row loads/errors as one unit rather than four
    // independently-timed cards. The allocations query is disabled
    // whenever a usable run exists, so it only contributes here in
    // the fallback case.
    stats,
    isStatsLoading:
      summaryQuery.isLoading ||
      isOptimizationHistoryPending ||
      productsQuery.isLoading ||
      appliedAllocationQuery.isLoading,
    isStatsError:
      summaryQuery.isError ||
      isCycleError ||
      optimizationHistoryQuery.isError ||
      productsQuery.isError ||
      appliedAllocationQuery.isError,

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

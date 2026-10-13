import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'

import { fetchResourceUtilization } from '../api/utilizationApi'
import {
  fetchFeasibility,
  fetchProductionAllocations,
} from '../api/productionAllocationApi'

import {
  toUiAtRiskResources,
  toUiBottlenecks,
  toUiResources,
  toUiSummary,
} from '../api/utilizationAdapter'

import useLatestProductionCycle from '../../../hooks/useLatestProductionCycle'

const useResourceUtilization = () => {
  // Canonical resolution (created_at DESC, id DESC), shared with
  // Production Allocation so both pages always agree on which cycle
  // is current - see the Production Cycle Selection Consistency
  // Audit. No longer fetches the whole cycle list itself, and
  // explicitly uses the cycle-specific endpoint below rather than
  // the no-arg /api/resource-utilization (per the approved design -
  // the cycle id must be explicit here).
  const {
    cycleId: latestCycleId,
    hasCycle,
    isLoading: isCycleLoading,
    isError: isCycleError,
  } = useLatestProductionCycle()

  const utilizationQuery = useQuery({
    queryKey: ['resource-utilization', latestCycleId],
    queryFn: () => fetchResourceUtilization(latestCycleId!),
    enabled: latestCycleId !== null,
  })

  // Same ['production-allocations', cycleId] query key as
  // production-allocation/hooks/useProductionAllocation.ts - shared
  // verbatim (same convention as 'resources-all'/'cycle-resources'
  // elsewhere in this app) so this dedupes with that page's own
  // fetch rather than issuing a second request. Only used to know
  // whether ANY allocation has been applied yet, for the empty state
  // below - not a source of utilization numbers.
  const allocationsQuery = useQuery({
    queryKey: ['production-allocations', latestCycleId],
    queryFn: () => fetchProductionAllocations(latestCycleId!),
    enabled: latestCycleId !== null,
  })

  const hasAppliedAllocation = (allocationsQuery.data ?? []).length > 0

  // Same ['feasibility', cycleId] query key as
  // production-allocation/hooks/useProductionAllocation.ts - shared
  // verbatim so this dedupes with that page's own fetch rather than
  // issuing a second request, same convention as the
  // 'production-allocations' query above. Tells whether the last
  // APPLIED allocation (never the Adaptive Optimization preview,
  // which has no applied_at) still fits current resource capacity.
  const feasibilityQuery = useQuery({
    queryKey: ['feasibility', latestCycleId],
    queryFn: () => fetchFeasibility(latestCycleId!),
    enabled: latestCycleId !== null,
  })

  const needsReoptimization =
    feasibilityQuery.data?.needs_reoptimization ?? false
  const isAllocationInfeasible =
    feasibilityQuery.data?.is_feasible === false
  const appliedAt = feasibilityQuery.data?.applied_at ?? null
  const feasibilityBottlenecks = (
    feasibilityQuery.data?.bottlenecks ?? []
  ).map((bottleneck) => ({
    resourceName: bottleneck.resource_name,
    unit: bottleneck.unit,
    shortageQuantity: Number(bottleneck.shortage_quantity),
  }))

  const summary = useMemo(
    () =>
      utilizationQuery.data
        ? toUiSummary(utilizationQuery.data)
        : null,
    [utilizationQuery.data],
  )

  const resources = useMemo(
    () =>
      utilizationQuery.data
        ? toUiResources(utilizationQuery.data)
        : [],
    [utilizationQuery.data],
  )

  const bottlenecks = useMemo(
    () =>
      utilizationQuery.data
        ? toUiBottlenecks(utilizationQuery.data)
        : [],
    [utilizationQuery.data],
  )

  const atRiskResources = useMemo(
    () =>
      utilizationQuery.data
        ? toUiAtRiskResources(utilizationQuery.data)
        : [],
    [utilizationQuery.data],
  )

  return {
    hasCycle,
    cycleId: latestCycleId,
    hasAppliedAllocation,

    summary,
    resources,
    bottlenecks,
    atRiskResources,

    isLoading:
      isCycleLoading
      || utilizationQuery.isLoading
      || allocationsQuery.isLoading,
    isError:
      isCycleError
      || utilizationQuery.isError
      || allocationsQuery.isError,

    needsReoptimization,
    isAllocationInfeasible,
    appliedAt,
    feasibilityBottlenecks,
    isFeasibilityLoading: feasibilityQuery.isLoading,
    isFeasibilityError: feasibilityQuery.isError,
  }
}

export default useResourceUtilization

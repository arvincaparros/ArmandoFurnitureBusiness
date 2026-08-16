import { useQuery } from '@tanstack/react-query'

import { fetchLatestProductionCycle } from '../api/productionCycle'

// Single shared resolution of "the latest production cycle", used by
// every module that needs to know which cycle is current (Production
// Allocation, Resource Utilization, and any future one) - replaces
// each module's own duplicated "fetch the whole list, take the last
// item" logic, per the Production Cycle Selection Consistency Audit.
const useLatestProductionCycle = () => {
  const query = useQuery({
    queryKey: ['production-cycles', 'latest'],
    queryFn: fetchLatestProductionCycle,
  })

  return {
    cycleId: query.data?.id ?? null,
    hasCycle: query.data !== null && query.data !== undefined,
    isLoading: query.isLoading,
    isError: query.isError,
  }
}

export default useLatestProductionCycle

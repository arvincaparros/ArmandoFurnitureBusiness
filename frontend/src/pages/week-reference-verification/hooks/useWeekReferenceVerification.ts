import { useCallback, useMemo, useState } from 'react'

import { useMutation, useQuery } from '@tanstack/react-query'

import {
  compareWeekReference,
  listWeekReferences,
} from '../api/weekReferenceApi'

const useWeekReferenceVerification = () => {
  const [selectedWeek, setSelectedWeek] = useState<number>(1)
  const [resourceOverrides, setResourceOverrides] = useState<
    Record<string, number>
  >({})

  const weeksQuery = useQuery({
    queryKey: ['week-references'],
    queryFn: listWeekReferences,
  })

  const currentWeek = useMemo(
    () =>
      (weeksQuery.data ?? []).find(
        (week) => week.week === selectedWeek,
      ) ?? null,
    [weeksQuery.data, selectedWeek],
  )

  const selectWeek = useCallback((week: number) => {
    setSelectedWeek(week)
    setResourceOverrides({})
  }, [])

  const setResourceOverride = useCallback(
    (resourceKey: string, value: number) => {
      setResourceOverrides((previous) => ({
        ...previous,
        [resourceKey]: value,
      }))
    },
    [],
  )

  const resetOverrides = useCallback(() => {
    setResourceOverrides({})
  }, [])

  const compareMutation = useMutation({
    mutationFn: () => {
      const hasOverrides = Object.keys(resourceOverrides).length > 0

      return compareWeekReference(
        selectedWeek,
        hasOverrides ? resourceOverrides : undefined,
      )
    },
  })

  return {
    weeks: weeksQuery.data ?? [],
    isLoadingWeeks: weeksQuery.isLoading,
    isWeeksError: weeksQuery.isError,

    selectedWeek,
    selectWeek,
    currentWeek,

    resourceOverrides,
    setResourceOverride,
    resetOverrides,

    runComparison: () => compareMutation.mutateAsync(),
    result: compareMutation.data ?? null,
    isComparing: compareMutation.isPending,
    compareError: compareMutation.error,
  }
}

export default useWeekReferenceVerification

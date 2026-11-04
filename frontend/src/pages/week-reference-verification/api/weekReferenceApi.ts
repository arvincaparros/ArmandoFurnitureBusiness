import apiClient from '../../../api/client'

import type {
  WeekReferenceCompareResult,
  WeekReferenceSummary,
} from './weekReferenceTypes'

export async function listWeekReferences(): Promise<
  WeekReferenceSummary[]
> {
  const response = await apiClient.get<WeekReferenceSummary[]>(
    '/api/week-references',
  )

  return response.data
}

export async function compareWeekReference(
  week: number,
  resourceOverrides?: Record<string, number>,
): Promise<WeekReferenceCompareResult> {
  const response = await apiClient.post<WeekReferenceCompareResult>(
    `/api/week-references/${week}/compare`,
    { resource_overrides: resourceOverrides ?? null },
  )

  return response.data
}

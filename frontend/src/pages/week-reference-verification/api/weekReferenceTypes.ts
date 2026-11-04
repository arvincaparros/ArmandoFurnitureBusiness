export interface WeekReferenceResourceSummary {
  available: string
  consumed: string | null
  unit: string
  name: string
}

export interface WeekReferenceSummary {
  week: number
  is_verified: boolean
  resources: Record<string, WeekReferenceResourceSummary>
  reference_allocation: Record<string, number>
  reference_total: number
  reference_profit: string
}

export interface ResourceUsageRow {
  available: string
  consumed: string
  remaining: string
  utilization_rate: string
}

export type ReferenceMatchStatus =
  | 'EXACT_MATCH'
  | 'MODIFIED_INPUT'
  | 'REFERENCE_INPUT_MISMATCH'

export interface WeekReferenceCompareResult {
  week: number
  is_modified_input: boolean
  reference_match_status: ReferenceMatchStatus
  resources_used: Record<string, string>
  resource_usage: Record<string, ResourceUsageRow>
  status: string
  computed_allocation: Record<string, number>
  reference_allocation: Record<string, number>
  allocation_difference: Record<string, number>
  allocation_matches_reference: boolean
  computed_total: number
  reference_total: number
  computed_profit: string
  reference_profit: string
  profit_matches_reference: boolean
}

// utilizationRate/totalRawMaterials (backend's overall_utilization_rate/
// total_raw_materials_consumed) were removed from here deliberately -
// both blend incompatible units (kg + hours + pcs) into one
// meaningless ratio/quantity (see the Resource Utilization
// investigation report). materialResourceCount and mostConstrained
// below are the unit-safe replacements the UI now shows instead.
import type { UtilizationStatus } from './utilizationStatus'

export interface UtilizationSummary {
  materialResourceCount: number
  mostConstrained: UtilizationResource | null

  laborUsed: number
  laborCapacity: number

  machineUsed: number
  machineCapacity: number
}

// Kept only so the now-unused UtilizationPieChart.tsx (superseded by
// UtilizationBarChart.tsx per this integration - see the report)
// still type-checks; no longer produced by the adapter or consumed
// by the page.
export interface PieChartData {
  name: string
  value: number
  color: string
}

export interface UtilizationResource {
  id: number

  resourceName: string
  unit: string

  totalConsumed: number

  totalRemaining: number

  utilizationPercent: number

  // "normal" | "high" | "at_risk" | "bottleneck" - see
  // utilizationStatus.ts for the display mapping. Also used for the
  // at-risk list (same shape - see utilizationAdapter.ts).
  status: UtilizationStatus
}

// Matches backend/app/schemas/utilization.py's ResourceBottleneck
// exactly, plus a derived `reason` sentence built from is_binding/
// shortageQuantity (see utilizationAdapter.ts) - there is no
// backend-provided free-text reason or recommendation field, so no
// `recommendation` field exists here (the old mock's version was
// never backed by anything real).
export interface Bottleneck {
  id: number

  resource: string
  unit: string

  remainingQuantity: number
  isBinding: boolean
  shortageQuantity: number

  reason: string
}

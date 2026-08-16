import type { ResourceUtilizationRunResponse } from './utilizationHistoryTypes'

import type { UtilizationHistoryRow } from '../types'

import { resolveUtilizationStatus } from '../../resource-utilization-report/utilizationStatus'

// Same Decimal-as-JSON-string convention used throughout this
// backend - duplicated locally rather than imported, matching this
// codebase's per-module convention (see e.g. productAdapter.ts/
// resourceAdapter.ts, each with their own copy).
function parseDecimal(value: string): number {
  const parsed = Number(value)

  return Number.isFinite(parsed) ? parsed : 0
}

// generated_at is a full ISO datetime, only reformatted for display
// (T -> space, drop fractional seconds), never reinterpreted - same
// pattern as optimizationHistoryAdapter.ts's toDisplayDate.
function toDisplayDate(generatedAt: string): string {
  return generatedAt.replace('T', ' ').split('.')[0]
}

// Flattens one run's detail response into one row per resource item -
// Utilization ID/Date Generated are intentionally repeated per row
// (see types.ts) to match the client's own requested column layout,
// rather than a summary-row + expand/modal structure.
export function toUiHistoryRows(
  run: ResourceUtilizationRunResponse,
): UtilizationHistoryRow[] {
  return run.items.map((item) => ({
    id: item.id,
    utilizationNumber: run.utilization_number,
    generatedAt: toDisplayDate(run.generated_at),
    resourceName: item.resource_name,
    unit: item.unit,
    consumedQuantity: parseDecimal(item.consumed_quantity),
    remainingQuantity: parseDecimal(item.remaining_quantity),
    utilizationPercent: parseDecimal(item.utilization_rate),
    status: resolveUtilizationStatus(item.status),
  }))
}

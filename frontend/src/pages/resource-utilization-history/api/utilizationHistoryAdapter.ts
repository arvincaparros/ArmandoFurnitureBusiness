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

// generated_at is always UTC (app/database/models.py::
// ResourceUtilizationRun.generated_at uses default=datetime.utcnow),
// but FastAPI/Pydantic serializes a naive datetime with NO "Z" or
// offset suffix (confirmed: e.g. "2026-08-17T11:25:44.982352") - and
// the JS Date constructor treats an offset-less ISO date-time string
// as already being LOCAL time, not UTC (confirmed:
// new Date("2026-08-17T09:01:27") reports itself as 09:01:27 in the
// browser's own zone, unshifted). The previous plain string reformat
// here never parsed the value as a Date at all, so it displayed the
// raw UTC clock digits as if they were already local - off by exactly
// the browser's UTC offset (e.g. 8 hours behind Philippine time).
//
// Appending "Z" only when the string doesn't already carry a
// timezone marker tells Date the source is UTC, so the getters below
// (local, not UTC, accessors) perform exactly one correct UTC -> local
// conversion for display - never a second one.
function toDisplayDate(generatedAt: string): string {
  const hasTimezone = /(Z|[+-]\d{2}:?\d{2})$/.test(generatedAt)
  const date = new Date(
    hasTimezone ? generatedAt : `${generatedAt}Z`,
  )

  const pad = (value: number) => String(value).padStart(2, '0')

  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  )
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

import type { OptimizationHistoryRunResponse } from './optimizationHistoryTypes'
import type { OptimizationHistory, ProfitTrend } from '../types'

// Every backend Decimal field arrives as a JSON string, never a bare
// number - see backend/docs/demand-forecasting-api-contract.md §14
// for the same behavior documented on another module.
function parseDecimal(value: string | null): number {
  if (value === null) {
    return 0
  }

  const parsed = Number(value)

  return Number.isFinite(parsed) ? parsed : 0
}

// started_at is a full ISO datetime ("2026-08-15T20:53:57.901496") -
// only reformatted for display (T -> space, drop fractional seconds),
// never reinterpreted or recalculated.
function toDisplayDate(startedAt: string): string {
  return startedAt.replace('T', ' ').split('.')[0]
}

function toOptimizationId(id: number): string {
  return `OP-${id}`
}

export function toUiOptimizationHistory(
  runs: OptimizationHistoryRunResponse[],
): OptimizationHistory[] {
  return runs.map((run) => ({
    id: run.id,
    optimizationId: toOptimizationId(run.id),
    dateGenerated: toDisplayDate(run.started_at),
    // duration_ms is nullable in the schema, but every existing
    // write path (save_optimization_history) always computes it -
    // this is a defensive fallback, not evidence of a real gap.
    duration: run.duration_ms ?? 0,
    totalProfit: parseDecimal(run.total_profit),
    // No total-cost/total-revenue field exists anywhere on this
    // response (confirmed against backend/app/schemas/
    // optimization_history.py) - null here, not a fabricated 0 or
    // derived estimate. OptimizationHistoryTable renders this as an
    // explained dash rather than a number.
    totalProductionCost: null,
    // Not provided by the backend as a count; the closest honest,
    // non-fabricated equivalent is the total recommended quantity
    // across this run's results - a display-only sum of real values
    // already returned by this same run, not a recalculation of the
    // optimization algorithm itself.
    productsProduced: run.results.reduce(
      (total, result) =>
        total + parseDecimal(result.recommended_quantity),
      0,
    ),
  }))
}

// Chart reads left-to-right as a chronological trend, so the
// (newest-first) history order is reversed here - a presentation
// reorder of already-fetched data, not a recalculation.
export function toUiProfitTrend(
  runs: OptimizationHistoryRunResponse[],
): ProfitTrend[] {
  return [...runs]
    .reverse()
    .map((run) => ({
      optimizationId: toOptimizationId(run.id),
      profit: parseDecimal(run.total_profit),
    }))
}

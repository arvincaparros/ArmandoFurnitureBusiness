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

// Distinct from parseDecimal above: null must stay null (a run saved
// before total_cost existed, or any other genuinely-unknown figure),
// never coerced to a fabricated 0 - same convention
// productionAdapter.ts's parseNullableDecimal already uses for
// cost/profit fields.
function parseNullableDecimal(value: string | null): number | null {
  if (value === null) {
    return null
  }

  const parsed = Number(value)

  return Number.isFinite(parsed) ? parsed : null
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
    // duration_ms is what the backend persists (save_optimization_
    // history derives it from the run's own start/end timestamps), but
    // this page mirrors a source spreadsheet that records seconds -
    // converted for display only, never rounded, so 599400 ms shows as
    // exactly 599.4 s.
    duration: (run.duration_ms ?? 0) / 1000,
    totalProfit: parseDecimal(run.total_profit),
    // A solve-time snapshot from the backend (build_optimization_
    // result()'s own total_cost, persisted the moment this run was
    // saved - see backend/app/services/optimization_history.py) -
    // null only for a run saved before that column existed, never a
    // fabricated 0 or a value derived from current prices.
    // OptimizationHistoryTable renders null as an explained dash.
    totalProductionCost: parseNullableDecimal(run.total_cost),
    // An imported historical record stores this aggregate directly,
    // because it deliberately carries no per-product results to sum
    // (is_summary_only) - showing the stored figure is what keeps this
    // page matching the source spreadsheet instead of reading 0.
    // Native runs leave products_produced null and keep the derived
    // sum: a display-only total of real values already returned by
    // this same run, not a recalculation of the optimization itself.
    productsProduced:
      run.products_produced !== null
        ? run.products_produced
        : run.results.reduce(
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

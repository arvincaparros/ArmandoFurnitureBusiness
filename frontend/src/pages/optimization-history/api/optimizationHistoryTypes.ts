// Mirrors backend/app/schemas/optimization_history.py exactly.
// total_cost is a snapshot taken at solve time (from the same
// build_optimization_result() figure the /optimize response itself
// returns) - null for any run saved before that column existed, and
// permanently null for those, never backfilled from current prices.
// See optimizationHistoryAdapter.ts for how the UI handles that null
// honestly rather than fabricating a value. All Decimal fields arrive
// as JSON strings, never bare numbers, matching every other Decimal
// field in this backend.

export interface OptimizationHistoryResultResponse {
  id: number
  product_id: number
  recommended_quantity: string
  unit_profit: string
  total_profit: string
}

export interface OptimizationHistoryRunResponse {
  id: number
  production_cycle_id: number
  started_at: string
  completed_at: string | null
  duration_ms: number | null
  status: string
  objective_value: string | null
  total_profit: string | null
  total_cost: string | null
  // Set only on an imported summary-only record, which has no
  // per-product results to sum - see optimizationHistoryAdapter.ts.
  products_produced: number | null
  // True when this run carries aggregate figures only: no results are
  // invented for it, and it is never an applyable plan.
  is_summary_only: boolean
  results: OptimizationHistoryResultResponse[]
}

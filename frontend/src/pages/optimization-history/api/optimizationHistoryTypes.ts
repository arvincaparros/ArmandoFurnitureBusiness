// Mirrors backend/app/schemas/optimization_history.py exactly. Notably
// absent: any total-cost/total-revenue field - GET /api/optimization/
// history only ever exposes total_profit (and objective_value) per
// run, never a production-cost breakdown. See optimizationHistoryAdapter.ts
// for how the UI handles that gap honestly rather than fabricating a
// value. All Decimal fields arrive as JSON strings, never bare numbers,
// matching every other Decimal field in this backend.

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
  results: OptimizationHistoryResultResponse[]
}

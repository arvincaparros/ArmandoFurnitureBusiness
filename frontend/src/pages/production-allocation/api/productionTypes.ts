// Mirrors backend/app/schemas/optimization.py,
// optimization_history.py, and production.py exactly.

export interface ProductionCycleResponse {
  id: number
  cycle_date: string
  start_date: string
  end_date: string
  status: string
}

// POST /{cycle_id}/optimize response - a fresh, just-computed
// result. Note quantity here is a plain int (not a Decimal string),
// and product_name IS included - unlike the history endpoint below.
export interface OptimizationAllocation {
  product_id: number
  product_name: string
  quantity: number
  unit_profit: string
  total_profit: string
}

export interface OptimizationResponse {
  cycle_id: number
  status: string
  objective: string
  total_revenue: string
  total_cost: string
  total_profit: string
  allocations: OptimizationAllocation[]
}

// GET /api/optimization/history response shape - a persisted run.
// No product_name (same gap as the Dashboard integration found),
// no total_revenue/total_cost (only total_profit) - see
// productionAdapter.ts for how these are derived when reading a
// persisted run instead of a fresh /optimize response.
export interface OptimizationHistoryResult {
  id: number
  product_id: number
  recommended_quantity: string
  unit_profit: string
  total_profit: string
}

export interface OptimizationHistoryResponse {
  id: number
  production_cycle_id: number
  started_at: string
  completed_at: string | null
  duration_ms: number | null
  status: string
  objective_value: string | null
  total_profit: string | null
  results: OptimizationHistoryResult[]
}

// Minimal slice of GET /api/products - only what's needed to resolve
// product_id -> name for a persisted history run's results.
export interface ProductSummary {
  id: number
  name: string
  selling_price: string
}

// GET /api/production-cycles/{cycle_id}/allocations - the ACTUAL
// committed production plan (backend/app/schemas/allocation.py).
// Distinct from both OptimizationResponse and
// OptimizationHistoryResponse above: this table is only ever written
// by POST /{cycle_id}/optimize/apply (verified in
// app/services/optimization.py::apply_optimization) or direct manual
// CRUD against this same endpoint - never by POST /optimize itself.
// No product_name here either - same bare-FK pattern as everywhere
// else in this backend.
export interface ProductionAllocationResponse {
  id: number
  production_cycle_id: number
  product_id: number
  quantity: string
}

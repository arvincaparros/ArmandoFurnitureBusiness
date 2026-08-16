// Backend wire shapes for everything the Dashboard composes together.
// Kept separate from ../types.ts, which holds the page's existing UI
// view-model types - see dashboardAdapter.ts for the translation
// between the two. Field names mirror the backend schemas exactly
// (backend/app/schemas/dashboard.py, optimization_history.py,
// utilization.py) - all Decimal fields arrive as JSON strings, never
// bare numbers, matching every other Decimal field in this backend.

export interface DashboardSummaryResponse {
  total_products: number
  total_resources: number
  total_production_cycles: number
  total_allocations: number
  total_optimization_runs: number
  latest_optimization_profit: string | null
  total_sales: string
  total_sales_profit: string
  latest_forecast_period: string | null
  latest_forecast_created_at: string | null
  latest_forecast_total_quantity: string | null
}

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

export interface ResourceUtilizationItem {
  resource_id: number
  resource_name: string
  resource_type: string
  unit: string
  available_quantity: string
  consumed_quantity: string
  remaining_quantity: string
  utilization_rate: string
}

export interface ResourceUtilizationResponse {
  cycle_id: number
  overall_utilization_rate: string
  total_raw_materials_consumed: string
  total_labor_hours_used: string
  total_labor_hours_capacity: string
  total_machine_hours_used: string
  total_machine_hours_capacity: string
  resources: ResourceUtilizationItem[]
  bottlenecks: unknown[]
}

// Minimal slice of GET /api/products - only what's needed to resolve
// product_id -> name (recommendations table) and product_id ->
// selling_price (expected revenue calculation).
export interface ProductSummary {
  id: number
  name: string
  selling_price: string
}

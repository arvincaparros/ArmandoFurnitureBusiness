import type {
  OptimizationHistoryResponse,
  OptimizationResponse,
  ProductionAllocationResponse,
  ProductSummary,
} from './productionTypes'

import type {
  OptimizationSummary,
  ProductionPlan,
} from '../types'

function parseDecimal(value: string | null | undefined): number {
  if (value === null || value === undefined) {
    return 0
  }

  const parsed = Number(value)

  return Number.isFinite(parsed) ? parsed : 0
}

// Distinct from parseDecimal above: null must stay null (Revision #2's
// "unavailable, never a silent 0" convention for cost/profit), not get
// coerced to 0 like a genuinely-absent/optional value would.
function parseNullableDecimal(
  value: string | null | undefined,
): number | null {
  if (value === null || value === undefined) {
    return null
  }

  const parsed = Number(value)

  return Number.isFinite(parsed) ? parsed : null
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString()
}

// /api/optimization/history is ordered newest-first (verified in
// backend/app/services/optimization_history.py, same as the
// Dashboard integration's finding). Only an OPTIMAL run represents a
// usable plan - a failed/infeasible run is treated as "no plan yet"
// rather than displayed.
export function findLatestOptimalRun(
  history: OptimizationHistoryResponse[] | undefined,
): OptimizationHistoryResponse | null {
  if (!history) {
    return null
  }

  return history.find((run) => run.status === 'OPTIMAL') ?? null
}

interface ProductionResult {
  plans: ProductionPlan[]
  summary: OptimizationSummary
}

// Fresh result straight from POST /{cycle_id}/optimize. This shape
// already includes product_name and total_revenue/total_cost
// directly - no product lookup needed for the aggregate summary,
// unlike fromHistoryRun below. Per-row Total Revenue (Revision #2)
// still needs a selling_price, which OptimizationAllocation doesn't
// carry - hence the `products` join here, same pattern fromHistoryRun
// already used. Per-row Total Cost is derived as revenue - the
// allocation's own total_profit (already the exact per-product value
// the ILP's objective function used - see calculate_unit_profit),
// never a second, independent cost calculation - so it's guaranteed
// to sum back to this response's own total_cost/total_revenue cards
// with no reconciliation risk. Start/end/duration aren't part of
// this response at all (verified - OptimizationResponse has no such
// fields), so they're measured client-side around the request; see
// the integration report for why that's a stated frontend
// derivation rather than a backend-sourced value.
export function fromOptimizeResponse(
  data: OptimizationResponse,
  timing: { startedAt: Date; completedAt: Date },
  products: ProductSummary[] | undefined,
): ProductionResult {
  const productsById = new Map(
    (products ?? []).map((product) => [product.id, product]),
  )

  const plans: ProductionPlan[] = data.allocations.map(
    (allocation) => {
      const sellingPrice = parseDecimal(
        productsById.get(allocation.product_id)?.selling_price,
      )

      const totalRevenue = allocation.quantity * sellingPrice
      const totalProfit = parseDecimal(allocation.total_profit)
      const totalCost = totalRevenue - totalProfit

      return {
        id: allocation.product_id,
        productName: allocation.product_name,
        quantity: allocation.quantity,
        totalRevenue,
        totalCost,
        totalProfit,
      }
    },
  )

  const durationMs =
    timing.completedAt.getTime() - timing.startedAt.getTime()

  return {
    plans,
    summary: {
      totalRevenue: parseDecimal(data.total_revenue),
      totalCost: parseDecimal(data.total_cost),
      totalProfit: parseDecimal(data.total_profit),
      startTime: timing.startedAt.toLocaleTimeString(),
      endTime: timing.completedAt.toLocaleTimeString(),
      duration: `${durationMs} ms`,
    },
  }
}

// A previously-persisted run, read back via /api/optimization/history
// (used on initial page load and after a refresh). This endpoint's
// results have no product_name (resolved via a product_id -> name
// lookup) and no total_revenue/total_cost (only total_profit) - so
// revenue is derived as recommended_quantity x selling_price per
// product, and cost is derived algebraically from
// revenue - profit (both are exact, not estimates, given the
// already-trusted total_profit value). Timing fields ARE real here -
// started_at/completed_at/duration_ms come straight from the
// persisted OptimizationRun.
export function fromHistoryRun(
  run: OptimizationHistoryResponse,
  products: ProductSummary[] | undefined,
): ProductionResult {
  const productsById = new Map(
    (products ?? []).map((product) => [product.id, product]),
  )

  const plans: ProductionPlan[] = run.results.map((result) => {
    const quantity = Math.round(
      parseDecimal(result.recommended_quantity),
    )

    const sellingPrice = parseDecimal(
      productsById.get(result.product_id)?.selling_price,
    )

    const totalRevenue = quantity * sellingPrice
    const totalProfit = parseDecimal(result.total_profit)
    const totalCost = totalRevenue - totalProfit

    return {
      id: result.product_id,
      productName:
        productsById.get(result.product_id)?.name ??
        `Product #${result.product_id}`,
      quantity,
      totalRevenue,
      totalCost,
      totalProfit,
    }
  })

  // Summed from the same per-row totalRevenue just computed above
  // (not a second, independent reduce over run.results) - guarantees
  // this reconciles with the row breakdown by construction rather
  // than by coincidence.
  const totalRevenue = plans.reduce(
    (sum, plan) => sum + plan.totalRevenue,
    0,
  )

  const totalProfit = parseDecimal(run.total_profit)
  const totalCost = totalRevenue - totalProfit

  return {
    plans,
    summary: {
      totalRevenue,
      totalCost,
      totalProfit,
      startTime: formatTime(run.started_at),
      endTime: run.completed_at
        ? formatTime(run.completed_at)
        : '—',
      duration:
        run.duration_ms === null
          ? '—'
          : `${run.duration_ms} ms`,
    },
  }
}

// The actual committed ProductionAllocation records, resolved with
// product names via a client-side join against /api/products - same
// join pattern as fromHistoryRun above, since this endpoint also
// only returns a bare product_id for the name. total_revenue/
// total_cost/total_profit (Revision #2) come straight from the
// backend's own get_allocations_with_financials computation - NOT
// re-derived here - since that's the one place with access to this
// cycle's CycleResource prices and each product's full requirement
// list (including inactive/unpriced ones), which the frontend doesn't
// otherwise fetch for this page. total_cost/total_profit are passed
// through as null, never coerced to 0, when the backend reports a
// required resource as currently unavailable.
export function fromAllocations(
  allocations: ProductionAllocationResponse[],
  products: ProductSummary[] | undefined,
): ProductionPlan[] {
  const productsById = new Map(
    (products ?? []).map((product) => [product.id, product]),
  )

  return allocations.map((allocation) => ({
    id: allocation.product_id,
    productName:
      productsById.get(allocation.product_id)?.name ??
      `Product #${allocation.product_id}`,
    quantity: Math.round(parseDecimal(allocation.quantity)),
    totalRevenue: parseDecimal(allocation.total_revenue),
    totalCost: parseNullableDecimal(allocation.total_cost),
    totalProfit: parseNullableDecimal(allocation.total_profit),
  }))
}

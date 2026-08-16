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
// directly - no product lookup or revenue derivation needed here,
// unlike fromHistoryRun below. Start/end/duration aren't part of
// this response at all (verified - OptimizationResponse has no such
// fields), so they're measured client-side around the request; see
// the integration report for why that's a stated frontend
// derivation rather than a backend-sourced value.
export function fromOptimizeResponse(
  data: OptimizationResponse,
  timing: { startedAt: Date; completedAt: Date },
): ProductionResult {
  const plans: ProductionPlan[] = data.allocations.map(
    (allocation) => ({
      id: allocation.product_id,
      productName: allocation.product_name,
      quantity: allocation.quantity,
    }),
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

  const plans: ProductionPlan[] = run.results.map((result) => ({
    id: result.product_id,
    productName:
      productsById.get(result.product_id)?.name ??
      `Product #${result.product_id}`,
    quantity: Math.round(parseDecimal(result.recommended_quantity)),
  }))

  const totalRevenue = run.results.reduce((sum, result) => {
    const price = parseDecimal(
      productsById.get(result.product_id)?.selling_price,
    )

    return (
      sum + parseDecimal(result.recommended_quantity) * price
    )
  }, 0)

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
// only returns a bare product_id.
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
  }))
}

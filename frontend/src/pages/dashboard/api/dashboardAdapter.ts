import {
  Archive,
  DollarSign,
  Package,
  TrendingUp,
} from 'lucide-react'

import type {
  DashboardSummaryResponse,
  OptimizationHistoryResponse,
  ProductSummary,
  ProductionAllocationFinancials,
  ResourceUtilizationResponse,
} from './dashboardTypes'

import type { DashboardStat } from '../types'

// Every backend Decimal field arrives as a JSON string, never a
// bare number - see backend/docs/demand-forecasting-api-contract.md
// §14 for the same behavior documented on another module. Centralize
// the parse here rather than scattering Number()/parseFloat() calls.
function parseDecimal(value: string | null | undefined): number | null {
  if (value === null || value === undefined) {
    return null
  }

  const parsed = Number(value)

  return Number.isFinite(parsed) ? parsed : null
}

function formatCurrency(value: number): string {
  return `₱${Math.round(value).toLocaleString('en-US')}`
}

function formatQuantity(value: number): string {
  return `${Math.round(value).toLocaleString('en-US')} units`
}

const NO_RUN_YET = 'No optimization run yet'

// Distinct from NO_RUN_YET: the committed allocation exists, but its
// profit cannot be priced because a required resource is currently
// inactive or unpriced. Showing a number there would understate it.
const PROFIT_UNAVAILABLE = 'Not available'

export interface DashboardRecommendation {
  id: number
  name: string
  quantity: string
  profit: string
}

export interface DashboardResourceUtilizationBar {
  name: string
  value: number
}

// --- Shared: latest OPTIMAL optimization run -----------------------
//
// /api/optimization/history has no "latest" endpoint and isn't
// filtered by status, so the latest OPTIMAL run is picked
// client-side from the newest-first list (verified ordering in
// backend/app/services/optimization_history.py). Resolved once and
// shared by both the recommendations table and the Expected Revenue
// stat, so they can never disagree about which run "latest" means -
// same run the summary endpoint uses for latest_optimization_profit.
// A summary-only imported record is skipped for the same reason the
// backend's get_latest_optimal_run excludes it: it has no
// product-level results, so it could neither price Expected Revenue
// nor produce a recommendation row.

export function findLatestOptimalRun(
  history: OptimizationHistoryResponse[] | undefined,
): OptimizationHistoryResponse | null {
  if (!history) {
    return null
  }

  return (
    history.find(
      (run) =>
        run.status === 'OPTIMAL' &&
        !run.is_summary_only &&
        run.results.length > 0,
    ) ?? null
  )
}

// --- Stat cards ------------------------------------------------------

function calculateExpectedRevenue(
  latestOptimalRun: OptimizationHistoryResponse | null,
  products: ProductSummary[] | undefined,
): number | null {
  if (!latestOptimalRun || !products) {
    return null
  }

  const priceById = new Map(
    products.map((product) => [
      product.id,
      parseDecimal(product.selling_price) ?? 0,
    ]),
  )

  return latestOptimalRun.results.reduce((total, result) => {
    const quantity = parseDecimal(result.recommended_quantity) ?? 0
    const price = priceById.get(result.product_id) ?? 0

    return total + quantity * price
  }, 0)
}

// --- Committed allocation fallback -----------------------------------
//
// The committed allocation is stored independently of any
// OptimizationRun, so it survives the approved Optimization History
// cleanup that deletes every old test run. The backend prices it
// from current cycle data (GET /api/production-cycles/{id}/
// allocations), which is exactly what the Dashboard shows once no
// usable run remains: real committed figures instead of two blank
// cards. Revenue always sums cleanly; profit falls back to
// unavailable as a whole the moment ANY row's profit is null - the
// same rule as ProductionPlanTable's overall total, so the card
// never silently understates it.

export interface AppliedAllocationSummary {
  revenue: number
  profit: number | null
}

export function summarizeAppliedAllocation(
  allocations: ProductionAllocationFinancials[] | undefined,
): AppliedAllocationSummary | null {
  if (!allocations || allocations.length === 0) {
    return null
  }

  const revenue = allocations.reduce(
    (total, allocation) =>
      total + (parseDecimal(allocation.total_revenue) ?? 0),
    0,
  )

  const profit = allocations.some(
    (allocation) => allocation.total_profit === null,
  )
    ? null
    : allocations.reduce(
        (total, allocation) =>
          total + (parseDecimal(allocation.total_profit) ?? 0),
        0,
      )

  return { revenue, profit }
}

export function buildDashboardStats(
  summary: DashboardSummaryResponse | undefined,
  latestOptimalRun: OptimizationHistoryResponse | null,
  products: ProductSummary[] | undefined,
  appliedAllocation?: AppliedAllocationSummary | null,
): DashboardStat[] {
  // A usable run always wins, so normal operation is unchanged. Only
  // when there is none (e.g. immediately after the cleanup deleted
  // the old runs) do the financial cards switch to the committed
  // allocation - which those deletions never touch.
  const usingAppliedAllocation =
    latestOptimalRun === null && appliedAllocation != null

  const expectedRevenue = latestOptimalRun
    ? calculateExpectedRevenue(latestOptimalRun, products)
    : (appliedAllocation?.revenue ?? null)

  const expectedProfit = latestOptimalRun
    ? summary
      ? parseDecimal(summary.latest_optimization_profit)
      : null
    : (appliedAllocation?.profit ?? null)

  const committedProfitUnavailable =
    latestOptimalRun === null &&
    appliedAllocation != null &&
    appliedAllocation.profit === null

  return [
    {
      id: 'active-resource-types',
      title: 'Active Resource Types',
      value: summary ? summary.total_resources : '—',
      description: 'Currently tracked resources',
      icon: Archive,
      color: 'blue',
    },
    {
      id: 'expected-revenue',
      title: 'Expected Revenue',
      value:
        expectedRevenue === null
          ? NO_RUN_YET
          : formatCurrency(expectedRevenue),
      description: usingAppliedAllocation
        ? 'Committed allocation × selling price'
        : 'Recommended quantity × selling price, latest optimal plan',
      icon: DollarSign,
      color: 'green',
    },
    {
      id: 'expected-profit',
      title: 'Expected Profit',
      value: committedProfitUnavailable
        ? PROFIT_UNAVAILABLE
        : expectedProfit === null
          ? NO_RUN_YET
          : formatCurrency(expectedProfit),
      description: committedProfitUnavailable
        ? 'Committed allocation has a required resource that is inactive or unpriced'
        : usingAppliedAllocation
          ? 'From the committed production allocation'
          : 'From the latest optimal production plan',
      icon: TrendingUp,
      color: 'orange',
    },
    {
      id: 'active-products',
      title: 'Active Products',
      value: summary ? summary.total_products : '—',
      description: 'Currently active in the catalog',
      icon: Package,
      color: 'grape',
    },
  ]
}

// --- Production recommendations table --------------------------------

export function buildDashboardRecommendations(
  latestOptimalRun: OptimizationHistoryResponse | null,
  products: ProductSummary[] | undefined,
): DashboardRecommendation[] {
  if (!latestOptimalRun || !products) {
    return []
  }

  const productNames = new Map(
    products.map((product) => [product.id, product.name]),
  )

  return latestOptimalRun.results.map((result) => {
    const quantity = parseDecimal(result.recommended_quantity) ?? 0
    const profit = parseDecimal(result.total_profit) ?? 0

    return {
      id: result.id,
      name:
        productNames.get(result.product_id) ??
        `Product #${result.product_id}`,
      quantity: formatQuantity(quantity),
      profit: formatCurrency(profit),
    }
  })
}

// --- Resource utilization bar chart -----------------------------------
//
// utilization_rate is used directly, unmodified (0-100, already
// per-resource comparable) - no normalization into pie-slice shares,
// since a horizontal bar chart doesn't need values to sum to 100 the
// way a pie's would.

export function buildDashboardResourceUtilization(
  utilization: ResourceUtilizationResponse | null | undefined,
): DashboardResourceUtilizationBar[] {
  if (!utilization) {
    return []
  }

  return utilization.resources.map((resource) => ({
    name: resource.resource_name,
    value: parseDecimal(resource.utilization_rate) ?? 0,
  }))
}

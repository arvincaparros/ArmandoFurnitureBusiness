import { describe, expect, it } from 'vitest'

import {
  buildDashboardStats,
  findLatestOptimalRun,
  summarizeAppliedAllocation,
} from './dashboardAdapter'

import type {
  DashboardSummaryResponse,
  OptimizationHistoryResponse,
  OptimizationHistoryResult,
  ProductSummary,
  ProductionAllocationFinancials,
} from './dashboardTypes'

function makeResult(id: number): OptimizationHistoryResult {
  return {
    id,
    product_id: id,
    recommended_quantity: '12.0000',
    unit_profit: '100.0000',
    total_profit: '1200.0000',
  }
}

function makeRun(
  overrides: Partial<OptimizationHistoryResponse> = {},
): OptimizationHistoryResponse {
  return {
    id: 171,
    production_cycle_id: 1,
    started_at: '2026-10-04T15:45:13',
    completed_at: '2026-10-04T15:55:20.200000',
    duration_ms: 607200,
    status: 'OPTIMAL',
    objective_value: '100490.5000',
    total_profit: '100490.5000',
    products_produced: 31,
    is_summary_only: true,
    results: [],
    ...overrides,
  }
}

const summary: DashboardSummaryResponse = {
  total_products: 23,
  total_resources: 10,
  total_production_cycles: 1,
  total_allocations: 10,
  total_optimization_runs: 8,
  latest_optimization_profit: null,
  total_sales: '0.0000',
  total_sales_profit: '0.0000',
  latest_forecast_period: null,
  latest_forecast_created_at: null,
  latest_forecast_total_quantity: null,
}

const products: ProductSummary[] = [
  { id: 1, name: 'Dining Table', selling_price: '12500.00' },
  { id: 2, name: 'Chair', selling_price: '3500.00' },
]

function makeAllocation(
  overrides: Partial<ProductionAllocationFinancials> = {},
): ProductionAllocationFinancials {
  return {
    id: 1,
    production_cycle_id: 1,
    product_id: 1,
    quantity: '5.0000',
    total_revenue: '62500.0000',
    total_cost: '1000.0000',
    total_profit: '61500.0000',
    ...overrides,
  }
}

// Two committed rows, 69,500 revenue and 68,000 profit - the figures
// the target database's preserved allocation produces.
const committedRows = [
  makeAllocation(),
  makeAllocation({
    id: 2,
    product_id: 2,
    quantity: '2.0000',
    total_revenue: '7000.0000',
    total_cost: '500.0000',
    total_profit: '6500.0000',
  }),
]

const statById = (
  stats: ReturnType<typeof buildDashboardStats>,
  id: string,
) => {
  const stat = stats.find((candidate) => candidate.id === id)

  if (!stat) {
    throw new Error(`Missing stat card: ${id}`)
  }

  return stat
}

describe('dashboard findLatestOptimalRun', () => {
  it('prefers the newest native run over an imported record', () => {
    const nativeRun = makeRun({
      id: 370,
      started_at: '2026-10-24T16:00:00',
      products_produced: null,
      is_summary_only: false,
      results: [makeResult(1)],
    })

    expect(
      findLatestOptimalRun([nativeRun, makeRun({ id: 171 })])?.id,
    ).toBe(370)
  })

  it('returns null rather than pricing a plan with no product rows', () => {
    expect(findLatestOptimalRun([makeRun({ id: 171 })])).toBeNull()
  })
})

describe('dashboard summarizeAppliedAllocation', () => {
  it('sums the committed rows while every row is priced', () => {
    expect(summarizeAppliedAllocation(committedRows)).toEqual({
      revenue: 69500,
      profit: 68000,
    })
  })

  it('returns null when nothing has been committed', () => {
    expect(summarizeAppliedAllocation(undefined)).toBeNull()
    expect(summarizeAppliedAllocation([])).toBeNull()
  })

  it('reports profit as unavailable when any row is unpriced', () => {
    expect(
      summarizeAppliedAllocation([
        makeAllocation(),
        makeAllocation({
          id: 2,
          total_revenue: '7000.0000',
          total_cost: null,
          total_profit: null,
        }),
      ]),
    ).toEqual({ revenue: 69500, profit: null })
  })
})

describe('dashboard buildDashboardStats fallback', () => {
  it('prices the committed allocation when no usable run exists', () => {
    const stats = buildDashboardStats(
      summary,
      null,
      products,
      summarizeAppliedAllocation(committedRows),
    )

    expect(statById(stats, 'expected-revenue').value).toBe('₱69,500')
    expect(statById(stats, 'expected-revenue').description).toBe(
      'Committed allocation × selling price',
    )

    expect(statById(stats, 'expected-profit').value).toBe('₱68,000')
    expect(statById(stats, 'expected-profit').description).toBe(
      'From the committed production allocation',
    )
  })

  it('shows the honest empty state without a run or an allocation', () => {
    const stats = buildDashboardStats(summary, null, products, null)

    expect(statById(stats, 'expected-revenue').value).toBe(
      'No optimization run yet',
    )
    expect(statById(stats, 'expected-profit').value).toBe(
      'No optimization run yet',
    )
  })

  it('does not understate an unpriced committed profit', () => {
    const stats = buildDashboardStats(
      summary,
      null,
      products,
      summarizeAppliedAllocation([
        makeAllocation(),
        makeAllocation({
          id: 2,
          total_revenue: '7000.0000',
          total_cost: null,
          total_profit: null,
        }),
      ]),
    )

    expect(statById(stats, 'expected-revenue').value).toBe('₱69,500')
    expect(statById(stats, 'expected-profit').value).toBe('Not available')
  })

  it('keeps the latest run authoritative when one exists', () => {
    const run = makeRun({
      id: 370,
      started_at: '2026-10-24T16:00:00',
      products_produced: null,
      is_summary_only: false,
      results: [makeResult(1)],
    })

    const stats = buildDashboardStats(
      { ...summary, latest_optimization_profit: '120000.0000' },
      run,
      products,
      summarizeAppliedAllocation(committedRows),
    )

    // 12 recommended units × ₱12,500 selling price.
    expect(statById(stats, 'expected-revenue').value).toBe('₱150,000')
    expect(statById(stats, 'expected-revenue').description).toBe(
      'Recommended quantity × selling price, latest optimal plan',
    )
    expect(statById(stats, 'expected-profit').value).toBe('₱120,000')
  })
})

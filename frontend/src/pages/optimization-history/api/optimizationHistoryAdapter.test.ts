import { describe, expect, it } from 'vitest'

import { toUiOptimizationHistory } from './optimizationHistoryAdapter'

import type { OptimizationHistoryRunResponse } from './optimizationHistoryTypes'

function makeRun(
  overrides: Partial<OptimizationHistoryRunResponse> = {},
): OptimizationHistoryRunResponse {
  return {
    id: 164,
    production_cycle_id: 1,
    started_at: '2026-08-16T15:40:18',
    completed_at: '2026-08-16T15:50:17.400000',
    duration_ms: 599400,
    status: 'OPTIMAL',
    objective_value: '102236.8100',
    total_profit: '102236.8100',
    total_cost: '126162.8400',
    products_produced: null,
    is_summary_only: false,
    results: [],
    ...overrides,
  }
}

describe('toUiOptimizationHistory', () => {
  it('shows the stored Products Produced for an imported summary-only record', () => {
    const [row] = toUiOptimizationHistory([
      makeRun({
        products_produced: 40,
        is_summary_only: true,
        results: [],
      }),
    ])

    expect(row.productsProduced).toBe(40)
  })

  it('still derives Products Produced from the results for a native run', () => {
    const [row] = toUiOptimizationHistory([
      makeRun({
        products_produced: null,
        results: [
          {
            id: 1,
            product_id: 1,
            recommended_quantity: '12.0000',
            unit_profit: '100.0000',
            total_profit: '1200.0000',
          },
          {
            id: 2,
            product_id: 2,
            recommended_quantity: '3.5000',
            unit_profit: '50.0000',
            total_profit: '175.0000',
          },
        ],
      }),
    ])

    expect(row.productsProduced).toBe(15.5)
  })

  it('converts the backend duration_ms to the seconds the source records use', () => {
    const [row] = toUiOptimizationHistory([makeRun()])

    expect(row.duration).toBe(599.4)
  })

  it('keeps the stored start date/time and solves nothing client-side', () => {
    const [row] = toUiOptimizationHistory([makeRun()])

    expect(row.optimizationId).toBe('OP-164')
    expect(row.dateGenerated).toBe('2026-08-16 15:40:18')
    expect(row.totalProfit).toBe(102236.81)
    expect(row.totalProductionCost).toBe(126162.84)
  })

  it('shows the eight imported records plus any later native run, with no fixed cap', () => {
    const imported = Array.from({ length: 8 }, (_, index) =>
      makeRun({
        id: 164 + index,
        products_produced: 40 + index,
        is_summary_only: true,
        results: [],
      }),
    )

    const nativeRun = makeRun({
      id: 370,
      started_at: '2026-11-02T09:15:00',
      duration_ms: 123400,
      products_produced: null,
      is_summary_only: false,
      results: [
        {
          id: 1,
          product_id: 1,
          recommended_quantity: '12.0000',
          unit_profit: '100.0000',
          total_profit: '1200.0000',
        },
      ],
    })

    const rows = toUiOptimizationHistory([nativeRun, ...imported])

    expect(rows).toHaveLength(9)
    expect(rows.map((row) => row.optimizationId)).toEqual([
      'OP-370',
      'OP-164',
      'OP-165',
      'OP-166',
      'OP-167',
      'OP-168',
      'OP-169',
      'OP-170',
      'OP-171',
    ])
    expect(rows[0].duration).toBe(123.4)
    expect(rows[0].productsProduced).toBe(12)
    expect(rows[8].productsProduced).toBe(47)
  })
})

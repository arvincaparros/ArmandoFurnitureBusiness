import { describe, expect, it } from 'vitest'

import { findLatestOptimalRun, fromOptimizeResponse } from './productionAdapter'

import type {
  OptimizationHistoryResponse,
  OptimizationHistoryResult,
  OptimizationResponse,
} from './productionTypes'

function makeResult(id: number): OptimizationHistoryResult {
  return {
    id,
    product_id: id,
    recommended_quantity: '12.0000',
    unit_profit: '100.0000',
    total_profit: '1200.0000',
    minimum_demand: '0.0000',
    shortfall: '0.0000',
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

describe('findLatestOptimalRun', () => {
  it('skips a newer summary-only record and keeps the live plan', () => {
    const summaryRun = makeRun({ id: 171 })

    const liveRun = makeRun({
      id: 191,
      started_at: '2026-10-24T15:45:49',
      products_produced: null,
      is_summary_only: false,
      results: [makeResult(1)],
    })

    expect(findLatestOptimalRun([summaryRun, liveRun])?.id).toBe(191)
  })

  it('never treats an OPTIMAL run with no results as an applyable plan', () => {
    const run = makeRun({
      id: 12,
      is_summary_only: false,
      products_produced: null,
      results: [],
    })

    expect(findLatestOptimalRun([run])).toBeNull()
  })

  it('returns null when only summary-only records exist', () => {
    expect(
      findLatestOptimalRun([makeRun({ id: 171 }), makeRun({ id: 170 })]),
    ).toBeNull()
  })

  it('still returns the newest usable OPTIMAL run', () => {
    const newer = makeRun({
      id: 20,
      is_summary_only: false,
      products_produced: null,
      results: [makeResult(1)],
    })

    const older = makeRun({
      id: 19,
      is_summary_only: false,
      products_produced: null,
      results: [makeResult(2)],
    })

    expect(findLatestOptimalRun([newer, older])?.id).toBe(20)
  })
})

function makeOptimizeResponse(
  woodRequired: string,
): OptimizationResponse {
  return {
    cycle_id: 1,
    status: 'OPTIMAL',
    objective: 'MAX_PROFIT',
    planning_mode: 'resource_based',
    total_revenue: '1000',
    total_cost: '500',
    total_profit: '500',
    allocations: [],
    resource_usage: [
      {
        resource_id: 1,
        resource_name: 'Wood',
        unit: 'board ft',
        required_quantity: woodRequired,
        available_quantity: '1000.0000',
        consumed_quantity: '0.0000',
        remaining_quantity: String(1000 - Number(woodRequired)),
        utilization_rate:
          ((Number(woodRequired) / 1000) * 100).toFixed(2),
        status: 'normal',
      },
    ],
  }
}

const timing = {
  startedAt: new Date('2026-11-04T10:00:00'),
  completedAt: new Date('2026-11-04T10:00:01'),
}

describe('fromOptimizeResponse resource utilization', () => {
  it('maps resource_usage straight through, scoped to this result only', () => {
    const result = fromOptimizeResponse(
      makeOptimizeResponse('400.0000'),
      timing,
      undefined,
    )

    expect(result.summary.resourceUsage).toEqual([
      {
        resourceId: 1,
        resourceName: 'Wood',
        unit: 'board ft',
        consumed: 400,
        remaining: 600,
        utilizationRate: 40,
        status: 'normal',
      },
    ])
  })

  it('a second call reflects only its own figures - never the first call summed in', () => {
    const first = fromOptimizeResponse(
      makeOptimizeResponse('400.0000'),
      timing,
      undefined,
    )

    const second = fromOptimizeResponse(
      makeOptimizeResponse('250.0000'),
      timing,
      undefined,
    )

    expect(first.summary.resourceUsage[0].consumed).toBe(400)

    // The second call's own figure (250), never 400 + 250 = 650.
    expect(second.summary.resourceUsage[0].consumed).toBe(250)
  })
})

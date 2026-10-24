import { describe, expect, it } from 'vitest'

import { findLatestOptimalRun } from './productionAdapter'

import type {
  OptimizationHistoryResponse,
  OptimizationHistoryResult,
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

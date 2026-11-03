import { describe, expect, it } from 'vitest'

import { toUiHistoryRows } from './utilizationHistoryAdapter'

import type {
  ResourceUtilizationHistoryItemResponse,
  ResourceUtilizationRunResponse,
} from './utilizationHistoryTypes'

function makeRun(
  items: ResourceUtilizationHistoryItemResponse[],
): ResourceUtilizationRunResponse {
  return {
    id: 1,
    utilization_number: 'UT-0001',
    production_cycle_id: 1,
    generated_at: '2026-11-02T10:00:00',
    items,
  }
}

function makeItem(
  overrides: Partial<ResourceUtilizationHistoryItemResponse> = {},
): ResourceUtilizationHistoryItemResponse {
  return {
    id: 1,
    resource_id: 1,
    resource_name: 'Test Labor',
    resource_type: 'labor',
    unit: 'hours',
    available_quantity: '500.0000',
    consumed_quantity: '250.0000',
    remaining_quantity: '250.0000',
    utilization_rate: '50.00',
    status: 'normal',
    ...overrides,
  }
}

describe('utilizationHistoryAdapter display capping', () => {
  it('passes through 50% utilization unchanged', () => {
    const [row] = toUiHistoryRows(
      makeRun([
        makeItem({
          consumed_quantity: '250.0000',
          remaining_quantity: '250.0000',
          utilization_rate: '50.00',
        }),
      ]),
    )

    expect(row.utilizationPercent).toBe(50)
    expect(row.remainingQuantity).toBe(250)
  })

  it('passes through exactly 100% utilization unchanged', () => {
    const [row] = toUiHistoryRows(
      makeRun([
        makeItem({
          consumed_quantity: '500.0000',
          remaining_quantity: '0.0000',
          utilization_rate: '100.00',
        }),
      ]),
    )

    expect(row.utilizationPercent).toBe(100)
    expect(row.remainingQuantity).toBe(0)
  })

  it('caps a stored 120% snapshot down to 100% displayed, with zero remaining', () => {
    const [row] = toUiHistoryRows(
      makeRun([
        makeItem({
          consumed_quantity: '600.0000',
          remaining_quantity: '-100.0000',
          utilization_rate: '120.00',
        }),
      ]),
    )

    expect(row.utilizationPercent).toBe(100)
    expect(row.remainingQuantity).toBe(0)
    // The stored snapshot's true consumption is still shown as-is.
    expect(row.consumedQuantity).toBe(600)
  })

  it('caps a stored 300% snapshot down to 100% displayed, with zero remaining', () => {
    const [row] = toUiHistoryRows(
      makeRun([
        makeItem({
          consumed_quantity: '1500.0000',
          remaining_quantity: '-1000.0000',
          utilization_rate: '300.00',
        }),
      ]),
    )

    expect(row.utilizationPercent).toBe(100)
    expect(row.remainingQuantity).toBe(0)
    expect(row.consumedQuantity).toBe(1500)
  })

  it('never displays a negative remaining quantity for a historical snapshot', () => {
    const [row] = toUiHistoryRows(
      makeRun([
        makeItem({
          consumed_quantity: '1152.0000',
          remaining_quantity: '-576.0000',
          utilization_rate: '200.00',
        }),
      ]),
    )

    expect(row.remainingQuantity).toBeGreaterThanOrEqual(0)
    expect(row.remainingQuantity).toBe(0)
  })
})

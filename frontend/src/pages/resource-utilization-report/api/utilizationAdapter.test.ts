import { describe, expect, it } from 'vitest'

import {
  toUiAtRiskResources,
  toUiBottlenecks,
  toUiResources,
  toUiSummary,
} from './utilizationAdapter'

import type {
  ResourceUtilizationItem,
  ResourceUtilizationResponse,
} from './utilizationTypes'

function makeItem(
  overrides: Partial<ResourceUtilizationItem> = {},
): ResourceUtilizationItem {
  return {
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

function makeResponse(
  resources: ResourceUtilizationItem[],
): ResourceUtilizationResponse {
  return {
    cycle_id: 1,
    overall_utilization_rate: '0.00',
    total_raw_materials_consumed: '0',
    total_labor_hours_used: '0',
    total_labor_hours_capacity: '0',
    total_machine_hours_used: '0',
    total_machine_hours_capacity: '0',
    material_resource_count: resources.length,
    most_constrained_resource: resources[0] ?? null,
    at_risk_resources: resources,
    resources,
    bottlenecks: [],
  }
}

describe('utilizationAdapter display capping', () => {
  it('passes through 50% utilization and remaining unchanged', () => {
    const [resource] = toUiResources(
      makeResponse([
        makeItem({
          available_quantity: '500.0000',
          consumed_quantity: '250.0000',
          remaining_quantity: '250.0000',
          utilization_rate: '50.00',
        }),
      ]),
    )

    expect(resource.utilizationPercent).toBe(50)
    expect(resource.totalRemaining).toBe(250)
    expect(resource.totalConsumed).toBe(250)
  })

  it('passes through exactly 100% utilization and zero remaining unchanged', () => {
    const [resource] = toUiResources(
      makeResponse([
        makeItem({
          available_quantity: '500.0000',
          consumed_quantity: '500.0000',
          remaining_quantity: '0.0000',
          utilization_rate: '100.00',
        }),
      ]),
    )

    expect(resource.utilizationPercent).toBe(100)
    expect(resource.totalRemaining).toBe(0)
  })

  it('caps 120% actual consumption down to 100% displayed, with zero remaining', () => {
    const [resource] = toUiResources(
      makeResponse([
        makeItem({
          available_quantity: '500.0000',
          consumed_quantity: '600.0000',
          remaining_quantity: '-100.0000',
          utilization_rate: '120.00',
        }),
      ]),
    )

    expect(resource.utilizationPercent).toBe(100)
    expect(resource.totalRemaining).toBe(0)
    // Actual consumption is never capped or hidden.
    expect(resource.totalConsumed).toBe(600)
  })

  it('caps 300% actual consumption down to 100% displayed, with zero remaining', () => {
    const [resource] = toUiResources(
      makeResponse([
        makeItem({
          available_quantity: '500.0000',
          consumed_quantity: '1500.0000',
          remaining_quantity: '-1000.0000',
          utilization_rate: '300.00',
        }),
      ]),
    )

    expect(resource.utilizationPercent).toBe(100)
    expect(resource.totalRemaining).toBe(0)
    expect(resource.totalConsumed).toBe(1500)
  })

  it('never displays a negative remaining quantity, however far over capacity', () => {
    const [resource] = toUiResources(
      makeResponse([
        makeItem({
          available_quantity: '576.0000',
          consumed_quantity: '1152.0000',
          remaining_quantity: '-576.0000',
          utilization_rate: '200.00',
        }),
      ]),
    )

    expect(resource.totalRemaining).toBeGreaterThanOrEqual(0)
    expect(resource.totalRemaining).toBe(0)
  })

  it('applies the same cap to the at-risk resources list and most-constrained resource', () => {
    const overAllocated = makeItem({
      resource_id: 2,
      resource_name: 'Test Epoxy',
      consumed_quantity: '24.0000',
      available_quantity: '8.0000',
      remaining_quantity: '-16.0000',
      utilization_rate: '300.00',
      status: 'bottleneck',
    })

    const response = makeResponse([overAllocated])

    const [atRisk] = toUiAtRiskResources(response)
    expect(atRisk.utilizationPercent).toBe(100)
    expect(atRisk.totalRemaining).toBe(0)

    const summary = toUiSummary(response)
    expect(summary.mostConstrained?.utilizationPercent).toBe(100)
    expect(summary.mostConstrained?.totalRemaining).toBe(0)
  })

  it('does not alter bottleneck shortage reporting, which stays uncapped on purpose', () => {
    const response = makeResponse([])
    response.bottlenecks = [
      {
        resource_id: 3,
        resource_name: 'Test Labor',
        unit: 'hours',
        remaining_quantity: '-576.0000',
        is_binding: false,
        shortage_quantity: '576.0000',
      },
    ]

    const [bottleneck] = toUiBottlenecks(response)

    expect(bottleneck.shortageQuantity).toBe(576)
    expect(bottleneck.reason).toContain('Over-allocated by 576')
  })
})

describe('toUiSummary labor/machine hours capping', () => {
  it('shows the true used hours when below capacity', () => {
    const response = makeResponse([])
    response.total_labor_hours_used = '400.0000'
    response.total_labor_hours_capacity = '480.0000'
    response.total_machine_hours_used = '600.0000'
    response.total_machine_hours_capacity = '672.0000'

    const summary = toUiSummary(response)

    expect(summary.laborUsed).toBe(400)
    expect(summary.laborCapacity).toBe(480)
    expect(summary.machineUsed).toBe(600)
    expect(summary.machineCapacity).toBe(672)
  })

  it('shows used hours unchanged when exactly at capacity', () => {
    const response = makeResponse([])
    response.total_labor_hours_used = '480.0000'
    response.total_labor_hours_capacity = '480.0000'
    response.total_machine_hours_used = '672.0000'
    response.total_machine_hours_capacity = '672.0000'

    const summary = toUiSummary(response)

    expect(summary.laborUsed).toBe(480)
    expect(summary.laborCapacity).toBe(480)
    expect(summary.machineUsed).toBe(672)
    expect(summary.machineCapacity).toBe(672)
  })

  it('caps used hours down to capacity when actual consumption exceeds it, leaving capacity unchanged', () => {
    // Example from the report: Labor 1800/480 -> displayed 480/480,
    // Machine 1304/672 -> displayed 672/672.
    const response = makeResponse([])
    response.total_labor_hours_used = '1800.0000'
    response.total_labor_hours_capacity = '480.0000'
    response.total_machine_hours_used = '1304.0000'
    response.total_machine_hours_capacity = '672.0000'

    const summary = toUiSummary(response)

    expect(summary.laborUsed).toBe(480)
    expect(summary.laborCapacity).toBe(480)
    expect(summary.machineUsed).toBe(672)
    expect(summary.machineCapacity).toBe(672)
  })
})

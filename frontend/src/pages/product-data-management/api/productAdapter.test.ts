import { describe, expect, it } from 'vitest'

import { buildResourceCostRates, toUiProduct } from './productAdapter'

import type { ProductResponse } from './productTypes'
import type { ResourceOption } from './productResourceTypes'
import type { ResolvedRequirement } from './productResourceAdapter'

function makeProduct(
  overrides: Partial<ProductResponse> = {},
): ProductResponse {
  return {
    id: 1,
    name: 'Ordinary Chair',
    selling_price: '3500.00',
    labor_cost: '300.00',
    minimum_demand: '3.0000',
    is_active: true,
    ...overrides,
  }
}

const wood: ResourceOption = {
  id: 10,
  name: 'Wood',
  resource_type: 'material',
  unit: 'board ft',
  is_active: true,
}

describe('toUiProduct minimumDemand', () => {
  it('maps the Decimal string "3.0000" to the integer 3', () => {
    const product = toUiProduct(makeProduct())

    expect(product.minimumDemand).toBe(3)
  })

  it('maps "0.0000" to 0 rather than treating it as absent', () => {
    const product = toUiProduct(
      makeProduct({ minimum_demand: '0.0000' }),
    )

    expect(product.minimumDemand).toBe(0)
  })

  it('preserves a positive minimumDemand when the cost breakdown is null', () => {
    // Wood is required but has no CycleResource price this cycle, so
    // costRates is empty and the whole cost breakdown comes back
    // null. minimumDemand is a real stored product field, not a
    // derived cost, so it must be unaffected.
    const requirements: ResolvedRequirement[] = [
      {
        id: 1,
        resourceId: wood.id,
        quantityRequired: 12,
        resourceName: wood.name,
        resourceUnit: wood.unit,
        resourceIsActive: true,
      },
    ]

    const product = toUiProduct(
      makeProduct({ minimum_demand: '5.0000' }),
      requirements,
      [wood],
      buildResourceCostRates([wood], []),
    )

    expect(product.totalCost).toBeNull()
    expect(product.laborCost).toBeNull()
    expect(product.minimumDemand).toBe(5)
  })

  it('preserves a 0 minimumDemand when the cost breakdown is null', () => {
    const requirements: ResolvedRequirement[] = [
      {
        id: 1,
        resourceId: wood.id,
        quantityRequired: 12,
        resourceName: wood.name,
        resourceUnit: wood.unit,
        resourceIsActive: true,
      },
    ]

    const product = toUiProduct(
      makeProduct({ minimum_demand: '0.0000' }),
      requirements,
      [wood],
      buildResourceCostRates([wood], []),
    )

    expect(product.totalCost).toBeNull()
    // Specifically not null and not undefined - a genuine 0.
    expect(product.minimumDemand).toBe(0)
  })
})

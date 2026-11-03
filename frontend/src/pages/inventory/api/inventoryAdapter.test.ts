import { describe, expect, it } from 'vitest'

import { toUiInventory } from './inventoryAdapter'

import type { InventoryOverviewResponse } from './inventoryTypes'

const response: InventoryOverviewResponse = {
  cycle_id: 3,
  cycle_start_date: '2026-10-25T00:00:00',
  cycle_end_date: '2026-11-01T00:00:00',
  stock_validation_enabled: true,
  products: [
    {
      product_id: 1,
      product_name: 'Ordinary Table',
      opening_quantity: '4.0000',
      total_produced: '20.0000',
      total_sold: '9.0000',
      available_stock: '15.0000',
      cycle_produced: '20.0000',
      cycle_sold: '9.0000',
    },
  ],
}

describe('toUiInventory', () => {
  it('parses every decimal string into a number', () => {
    const result = toUiInventory(response)

    expect(result.products[0]).toEqual({
      productId: 1,
      productName: 'Ordinary Table',
      openingQuantity: 4,
      totalProduced: 20,
      totalSold: 9,
      availableStock: 15,
      cycleProduced: 20,
      cycleSold: 9,
    })
  })

  it('carries the cycle window and the validation gate through', () => {
    const result = toUiInventory(response)

    expect(result.cycleId).toBe(3)
    expect(result.stockValidationEnabled).toBe(true)
  })

  it('survives a response with no production cycle', () => {
    const result = toUiInventory({
      ...response,
      cycle_id: null,
      cycle_start_date: null,
      cycle_end_date: null,
      stock_validation_enabled: false,
      products: [],
    })

    expect(result.cycleId).toBeNull()
    expect(result.stockValidationEnabled).toBe(false)
    expect(result.products).toEqual([])
  })
})

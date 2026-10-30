import type { Product } from '../types'

export const productData: Product[] = [
  {
    id: 1,
    productName: 'Dining Table (4 seat)',
    isActive: true,

    resourceQuantities: {},

    minimumDemand: 1,

    sellingPrice: 18000,

    materialCost: 0,
    laborCost: 1800,
    machineCost: 0,
    totalCost: 1800,
    profit: 16200,
  },
  {
    id: 2,
    productName: 'High Chair',
    isActive: true,

    resourceQuantities: {},

    minimumDemand: 0,

    sellingPrice: 6500,

    materialCost: 0,
    laborCost: 720,
    machineCost: 0,
    totalCost: 720,
    profit: 5780,
  },
]

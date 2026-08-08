import type { Product } from '../types'

export const productData: Product[] = [
  {
    id: 1,
    productName: 'Dining Table (4 seat)',

    wood: 40,
    epoxy: 2,
    nails: 50,
    glue: 1,
    sandpaper: 3,
    doorknob: 0,

    laborHours: 20,
    sawHours: 1,
    thicknessPlanerHours: 0.5,
    handPlanerHours: 1,

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

    wood: 10,
    epoxy: 0,
    nails: 20,
    glue: 1,
    sandpaper: 2,
    doorknob: 0,

    laborHours: 8,
    sawHours: 0.5,
    thicknessPlanerHours: 0.25,
    handPlanerHours: 0.25,

    sellingPrice: 6500,

    materialCost: 0,
    laborCost: 720,
    machineCost: 0,
    totalCost: 720,
    profit: 5780,
  },
]
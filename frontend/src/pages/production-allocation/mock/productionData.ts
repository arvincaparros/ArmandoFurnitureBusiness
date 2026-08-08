import type {
  OptimizationSummary,
  ProductionPlan,
} from '../types'

export const productionPlans: ProductionPlan[] = [
  {
    id: 1,
    productName: 'Dining Table',
    quantity: 12,
  },
  {
    id: 2,
    productName: 'Wardrobe',
    quantity: 6,
  },
  {
    id: 3,
    productName: 'Bookshelf',
    quantity: 15,
  },
  {
    id: 4,
    productName: 'Carved Chair',
    quantity: 24,
  },
]

export const optimizationSummary: OptimizationSummary =
  {
    totalRevenue: 285400,
    totalCost: 188680,
    totalProfit: 96720,

    startTime: '5:42:18 PM',
    endTime: '5:42:18 PM',
    duration: '808 ms',
  }
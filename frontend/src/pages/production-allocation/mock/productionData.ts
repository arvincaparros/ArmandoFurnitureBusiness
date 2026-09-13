import type {
  OptimizationSummary,
  ProductionPlan,
} from '../types'

export const productionPlans: ProductionPlan[] = [
  {
    id: 1,
    productName: 'Dining Table',
    quantity: 12,
    totalRevenue: 84000,
    totalCost: 54000,
    totalProfit: 30000,
  },
  {
    id: 2,
    productName: 'Wardrobe',
    quantity: 6,
    totalRevenue: 66000,
    totalCost: 42000,
    totalProfit: 24000,
  },
  {
    id: 3,
    productName: 'Bookshelf',
    quantity: 15,
    totalRevenue: 78000,
    totalCost: 51000,
    totalProfit: 27000,
  },
  {
    id: 4,
    productName: 'Carved Chair',
    quantity: 24,
    totalRevenue: 57400,
    totalCost: 41680,
    totalProfit: 15720,
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
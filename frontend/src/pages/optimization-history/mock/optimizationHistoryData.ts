import type {
  OptimizationHistory,
  ProfitTrend,
} from '../types'

export const optimizationHistory: OptimizationHistory[] = [
  {
    id: 1,
    optimizationId: 'OP-220',
    dateGenerated: '2026-06-06 08:16:02',
    duration: 812,
    totalProfit: 96720,
    totalProductionCost: 188680,
    productsProduced: 57,
  },
  {
    id: 2,
    optimizationId: 'OP-219',
    dateGenerated: '2026-06-05 17:04:31',
    duration: 765,
    totalProfit: 88150,
    totalProductionCost: 180750,
    productsProduced: 52,
  },
  {
    id: 3,
    optimizationId: 'OP-218',
    dateGenerated: '2026-06-04 13:22:19',
    duration: 910,
    totalProfit: 102400,
    totalProductionCost: 198800,
    productsProduced: 60,
  },
  {
    id: 4,
    optimizationId: 'OP-217',
    dateGenerated: '2026-06-03 08:10:44',
    duration: 688,
    totalProfit: 79800,
    totalProductionCost: 171200,
    productsProduced: 48,
  },
  {
    id: 5,
    optimizationId: 'OP-216',
    dateGenerated: '2026-06-02 11:33:51',
    duration: 745,
    totalProfit: 83900,
    totalProductionCost: 176500,
    productsProduced: 50,
  },
  {
    id: 6,
    optimizationId: 'OP-215',
    dateGenerated: '2026-06-01 09:15:00',
    duration: 650,
    totalProfit: 77500,
    totalProductionCost: 169000,
    productsProduced: 45,
  },
]

export const profitTrendData: ProfitTrend[] = [
  {
    optimizationId: 'OP-215',
    profit: 77500,
  },
  {
    optimizationId: 'OP-216',
    profit: 83900,
  },
  {
    optimizationId: 'OP-217',
    profit: 79800,
  },
  {
    optimizationId: 'OP-218',
    profit: 102400,
  },
  {
    optimizationId: 'OP-219',
    profit: 88150,
  },
  {
    optimizationId: 'OP-220',
    profit: 96720,
  },
]

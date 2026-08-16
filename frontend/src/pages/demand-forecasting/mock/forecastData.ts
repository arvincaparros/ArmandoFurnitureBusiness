import type {
  ChatMessage,
  ForecastChartData,
  ForecastItem,
} from '../types'

export const forecastItems: ForecastItem[] = [
  {
    id: 1,
    furnitureProduct: 'Dining Table (6-seater)',
    historicalSales: 280,
    predictedDemand: 315,
    forecastPeriod: 'Jul 2026',
    confidenceLevel: 91.2,
    status: 'READY',
  },
  {
    id: 2,
    furnitureProduct: 'Bookshelf Frame',
    historicalSales: 115,
    predictedDemand: 128,
    forecastPeriod: 'Jul 2026',
    confidenceLevel: 89.5,
    status: 'READY',
  },
  {
    id: 3,
    furnitureProduct: 'Wardrobe Cabinet',
    historicalSales: 75,
    predictedDemand: 83,
    forecastPeriod: 'Jul 2026',
    confidenceLevel: 90.1,
    status: 'READY',
  },
  {
    id: 4,
    furnitureProduct: 'Carved Chair',
    historicalSales: 310,
    predictedDemand: 352,
    forecastPeriod: 'Aug 2026',
    confidenceLevel: 92.0,
    status: 'READY',
  },
]

export const forecastChartData: ForecastChartData[] = [
  {
    month: "Jan '26",
    historicalDemand: 55,
  },
  {
    month: "Feb '26",
    historicalDemand: 100,
  },
  {
    month: "Mar '26",
    historicalDemand: 160,
  },
  {
    month: "Apr '26",
    historicalDemand: 210,
  },
  {
    month: "May '26",
    historicalDemand: 220,
    forecastedDemand: 220,
  },
  {
    month: "Jun '26",
    forecastedDemand: 255,
  },
  {
    month: "Jul '26",
    forecastedDemand: 285,
  },
  {
    month: "Aug '26",
    forecastedDemand: 315,
  },
]

export const chatMessages: ChatMessage[] = [
  {
    id: 1,
    role: 'assistant',
    message:
      "Hello, Admin! I've analyzed your sales history. To optimize production, which product category are you most concerned about for next month?",
  },
  {
    id: 2,
    role: 'user',
    message:
      "Can you summarize the predicted demand for the 'Dining Table' category for July 2026?",
  },
]
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

// Static shape reference only (nothing imports this module any more):
// matches ForecastChartData, whose x-axis field is the short `date`
// label, whose tooltip date is `fullDate`, and whose rows record
// whether they are historical or forecast.
export const forecastChartData: ForecastChartData[] = [
  {
    date: 'Jan 15',
    fullDate: 'Jan 15, 2026',
    isForecast: false,
    historicalDemand: 55,
  },
  {
    date: 'Feb 12',
    fullDate: 'Feb 12, 2026',
    isForecast: false,
    historicalDemand: 100,
  },
  {
    date: 'Mar 20',
    fullDate: 'Mar 20, 2026',
    isForecast: false,
    historicalDemand: 160,
  },
  {
    date: 'Apr 08',
    fullDate: 'Apr 08, 2026',
    isForecast: false,
    historicalDemand: 210,
  },
  {
    date: 'May 22',
    fullDate: 'May 22, 2026',
    isForecast: false,
    historicalDemand: 220,
    forecastedDemand: 220,
  },
  {
    date: 'Jun 01',
    fullDate: 'Jun 01, 2026',
    isForecast: true,
    forecastedDemand: 255,
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
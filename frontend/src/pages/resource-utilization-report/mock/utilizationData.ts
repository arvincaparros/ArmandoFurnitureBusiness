import type {
  Bottleneck,
  PieChartData,
  UtilizationResource,
  UtilizationSummary,
} from '../types'

export const resources: UtilizationResource[] = [
  {
    id: 1,
    resourceName: 'Wood',
    unit: 'board ft',
    totalConsumed: 478,
    totalRemaining: 22,
    utilizationPercent: 95.6,
    status: 'bottleneck',
  },
  {
    id: 2,
    resourceName: 'Epoxy',
    unit: 'liter',
    totalConsumed: 32,
    totalRemaining: 8,
    utilizationPercent: 80,
    status: 'high',
  },
  {
    id: 3,
    resourceName: 'Labor',
    unit: 'hours',
    totalConsumed: 480,
    totalRemaining: 96,
    utilizationPercent: 83.3,
    status: 'high',
  },
  {
    id: 4,
    resourceName: 'Circular Saw',
    unit: 'hrs',
    totalConsumed: 180,
    totalRemaining: 156,
    utilizationPercent: 53.6,
    status: 'normal',
  },
  {
    id: 5,
    resourceName: 'Wood Glue',
    unit: 'bottle',
    totalConsumed: 30,
    totalRemaining: 28,
    utilizationPercent: 25,
    status: 'normal',
  },
  {
    id: 6,
    resourceName: 'Sandpaper',
    unit: 'sheet',
    totalConsumed: 200,
    totalRemaining: 192,
    utilizationPercent: 44,
    status: 'normal',
  },
  {
    id: 7,
    resourceName: 'Doorknob',
    unit: 'pc',
    totalConsumed: 60,
    totalRemaining: 12,
    utilizationPercent: 48,
    status: 'normal',
  },
]

export const summary: UtilizationSummary = {
  materialResourceCount: 5,
  mostConstrained: resources[0],

  laborUsed: 480,
  laborCapacity: 576,

  machineUsed: 310,
  machineCapacity: 672,
}

export const pieChartData: PieChartData[] = [
  {
    name: 'Raw Materials',
    value: 55,
    color: 'brown.8',
  },
  {
    name: 'Labor',
    value: 30,
    color: 'orange.6',
  },
  {
    name: 'Machine Hours',
    value: 15,
    color: 'yellow.5',
  },
]

export const bottlenecks: Bottleneck[] = [
  {
    id: 1,
    resource: 'Wood',
    unit: 'board ft',
    remainingQuantity: 22,
    isBinding: false,
    shortageQuantity: 0,
    reason:
      'Inventory level reached usable capacity.',
  },
  {
    id: 2,
    resource: 'Circular Saw',
    unit: 'hrs',
    remainingQuantity: 0,
    isBinding: true,
    shortageQuantity: 0,
    reason:
      'Machine-hour capacity reached.',
  },
]

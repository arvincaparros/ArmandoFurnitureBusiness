import type {
  Bottleneck,
  PieChartData,
  UtilizationResource,
  UtilizationSummary,
} from '../types'

export const summary: UtilizationSummary = {
  utilizationRate: 81.4,

  totalRawMaterials: 2150,

  laborUsed: 480,
  laborCapacity: 576,

  machineUsed: 310,
  machineCapacity: 672,
}

export const resources: UtilizationResource[] = [
  {
    id: 1,
    resourceName: 'Wood (board ft)',
    totalConsumed: 478,
    totalRemaining: 22,
    utilizationPercent: 95.6,
  },
  {
    id: 2,
    resourceName: 'Epoxy (liter)',
    totalConsumed: 32,
    totalRemaining: 8,
    utilizationPercent: 80,
  },
  {
    id: 3,
    resourceName: 'Labor Hours',
    totalConsumed: 480,
    totalRemaining: 96,
    utilizationPercent: 83.3,
  },
  {
    id: 4,
    resourceName: 'Circular Saw (hrs)',
    totalConsumed: 180,
    totalRemaining: 156,
    utilizationPercent: 53.6,
  },
  {
    id: 5,
    resourceName: 'Wood Glue (bottle)',
    totalConsumed: 30,
    totalRemaining: 28,
    utilizationPercent: 25,
  },
  {
    id: 6,
    resourceName: 'Sandpaper (sheet)',
    totalConsumed: 200,
    totalRemaining: 192,
    utilizationPercent: 44,
  },
  {
    id: 7,
    resourceName: 'Doorknob (pc)',
    totalConsumed: 60,
    totalRemaining: 12,
    utilizationPercent: 48,
  },
]

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
    resource: 'Wood (board ft)',
    reason:
      'Inventory level reached usable capacity.',
    recommendation:
      'Increase wood stock.',
  },
  {
    id: 2,
    resource: 'Circular Saw',
    reason:
      'Machine-hour capacity reached.',
    recommendation:
      'Schedule additional saw shifts.',
  },
]

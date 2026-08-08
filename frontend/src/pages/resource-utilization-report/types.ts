export interface UtilizationSummary {
  utilizationRate: number

  totalRawMaterials: number

  laborUsed: number
  laborCapacity: number

  machineUsed: number
  machineCapacity: number
}

export interface UtilizationResource {
  id: number

  resourceName: string

  totalConsumed: number

  totalRemaining: number

  utilizationPercent: number
}

export interface PieChartData {
  name: string
  value: number
  color: string
}

export interface Bottleneck {
  id: number

  resource: string

  reason: string

  recommendation: string
}
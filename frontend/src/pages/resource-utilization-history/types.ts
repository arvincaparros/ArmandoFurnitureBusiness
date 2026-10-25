import type { UtilizationStatus } from '../resource-utilization-report/utilizationStatus'

// One row per resource within a utilization run - the snapshot number
// and Date Generated repeat across every resource belonging to the same
// run, so the table stays a flat list in the client's requested column
// layout (Date Generated | Resource | Consumed | Remaining |
// Utilization % | Status, multiple rows per snapshot) rather than a
// summary+expand/modal structure.
export interface UtilizationHistoryRow {
  id: number
  utilizationNumber: string
  generatedAt: string
  resourceName: string
  unit: string
  consumedQuantity: number
  remainingQuantity: number
  utilizationPercent: number
  status: UtilizationStatus
}

import type { UtilizationStatus } from '../resource-utilization-report/utilizationStatus'

// One row per resource within a utilization run - Utilization ID and
// Date Generated repeat across every resource belonging to the same
// run, per the client's own requested column layout (Utilization ID |
// Date Generated | Resource | Consumed | Remaining | Utilization % |
// Status, multiple rows per Utilization ID) rather than a
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

import { ScrollArea, Tooltip } from '@mantine/core'
import AppTable, {
  type Column,
} from '../../../components/tables/AppTable'

import type { OptimizationHistory } from '../types'

interface OptimizationHistoryTableProps {
  optimizationHistory: OptimizationHistory[]
  isLoading: boolean
  isError: boolean
}

const NO_COST_DATA =
  'Not provided by GET /api/optimization/history - this endpoint returns total_profit only, no production-cost figure.'

// Same explained-dash pattern used by ProductTable.tsx for backend
// fields that genuinely don't exist yet - explicit, not fabricated,
// not silently dropped.
const costDash = () => (
  <Tooltip label={NO_COST_DATA}>
    <span>—</span>
  </Tooltip>
)

const OptimizationHistoryTable = ({
  optimizationHistory,
  isLoading,
  isError,
}: OptimizationHistoryTableProps) => {
  const columns: Column<OptimizationHistory>[] = [
    {
      accessor: 'optimizationId',
      title: 'Optimization ID',
    },
    {
      accessor: 'dateGenerated',
      title: 'Date Generated',
    },
    {
      accessor: 'duration',
      title: 'Duration (ms)',
      textAlign: 'center',
    },
    {
      accessor: 'totalProfit',
      title: 'Total Profit',
      textAlign: 'right',
      render: (row) =>
        `₱${row.totalProfit.toLocaleString()}`,
    },
    {
      accessor: 'totalProductionCost',
      title: 'Total Production Cost',
      textAlign: 'right',
      render: (row) =>
        row.totalProductionCost === null
          ? costDash()
          : `₱${row.totalProductionCost.toLocaleString()}`,
    },
    {
      accessor: 'productsProduced',
      title: 'Products Produced',
      textAlign: 'center',
    },
  ]

  const emptyMessage = isLoading
    ? 'Loading optimization history...'
    : isError
      ? 'Unable to load optimization history.'
      : 'No optimization history found.'

  return (
    <ScrollArea
        type="auto"
        offsetScrollbars
    >
        <AppTable
            columns={columns}
            data={isLoading ? [] : optimizationHistory}
            emptyMessage={emptyMessage}
        />
    </ScrollArea>

  )
}

export default OptimizationHistoryTable

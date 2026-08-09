import { ScrollArea } from '@mantine/core'
import AppTable, {
  type Column,
} from '../../../components/tables/AppTable'

import type { OptimizationHistory } from '../types'

interface OptimizationHistoryTableProps {
  optimizationHistory: OptimizationHistory[]
}

const OptimizationHistoryTable = ({
  optimizationHistory,
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
        `₱${row.totalProductionCost.toLocaleString()}`,
    },
    {
      accessor: 'productsProduced',
      title: 'Products Produced',
      textAlign: 'center',
    },
  ]

  return (
    <ScrollArea
        type="auto"
        offsetScrollbars
    >
        <AppTable
            columns={columns}
            data={optimizationHistory}
            emptyMessage="No optimization history found."
        />
    </ScrollArea>
    
  )
}

export default OptimizationHistoryTable
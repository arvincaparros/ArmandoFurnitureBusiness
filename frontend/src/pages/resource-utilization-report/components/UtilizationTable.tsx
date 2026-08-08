import AppTable, {
  type Column,
} from '../../../components/tables/AppTable'

import UtilizationProgress from './UtilizationProgress'

import type { UtilizationResource } from '../types'
import { Progress, ScrollArea } from '@mantine/core'

interface UtilizationTableProps {
  resources: UtilizationResource[]
}

const UtilizationTable = ({
  resources,
}: UtilizationTableProps) => {
    const getColor = (value: number) => {
        if (value >= 90) return 'red'
        if (value >= 75) return 'yellow'
        return 'green'
    }

    const columns: Column<UtilizationResource>[] =
    [
      {
        accessor: 'resourceName',
        title: 'Resource',
      },
      {
        accessor: 'totalConsumed',
        title: 'Total Consumed',
      },
      {
        accessor: 'totalRemaining',
        title: 'Total Remaining',
      },
      {
        accessor: 'utilizationPercent',
        title: 'Overall Utilization %',
        render: (row) => (
          <UtilizationProgress
            value={
              row.utilizationPercent
            }
          />
        ),
      },
      {
        accessor: 'utilizationVisual',
        title: 'Utilization Visual',
        textAlign: 'center',
        render: (row) => (
            <Progress
                value={row.utilizationPercent}
                color={getColor(row.utilizationPercent)}
                radius="xl"
                size="sm"
                w={110}
            />
        ),
      },
    ]

  return (
    <ScrollArea
        type="auto"
        offsetScrollbars
    >
        <AppTable
        columns={columns}
        data={resources}
        emptyMessage="No utilization data."
        />
    </ScrollArea>
  )
}

export default UtilizationTable
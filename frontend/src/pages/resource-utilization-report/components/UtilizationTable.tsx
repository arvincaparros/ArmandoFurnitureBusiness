import AppTable, {
  type Column,
} from '../../../components/tables/AppTable'

import UtilizationProgress from './UtilizationProgress'

import type { UtilizationResource } from '../types'
import { Badge, ScrollArea } from '@mantine/core'

import { UTILIZATION_STATUS_META } from '../utilizationStatus'

interface UtilizationTableProps {
  resources: UtilizationResource[]
  isLoading: boolean
  isError: boolean
}

const UtilizationTable = ({
  resources,
  isLoading,
  isError,
}: UtilizationTableProps) => {
    const columns: Column<UtilizationResource>[] =
    [
      {
        accessor: 'resourceName',
        title: 'Resource',
      },
      {
        accessor: 'totalConsumed',
        title: 'Consumed',
        render: (row) =>
          `${row.totalConsumed} ${row.unit}`,
      },
      {
        accessor: 'totalRemaining',
        title: 'Remaining',
        render: (row) =>
          `${row.totalRemaining} ${row.unit}`,
      },
      {
        accessor: 'utilizationPercent',
        title: 'Utilization',
        render: (row) => (
          <UtilizationProgress
            value={row.utilizationPercent}
            status={row.status}
          />
        ),
      },
      {
        accessor: 'status',
        title: 'Status',
        textAlign: 'center',
        render: (row) => (
          <Badge
            color={UTILIZATION_STATUS_META[row.status].color}
            variant="light"
            size="sm"
          >
            {UTILIZATION_STATUS_META[row.status].label}
          </Badge>
        ),
      },
    ]

  const emptyMessage = isLoading
    ? 'Loading...'
    : isError
      ? 'Unable to load resource utilization.'
      : 'No utilization data for this production cycle.'

  return (
    <ScrollArea
        type="auto"
        offsetScrollbars
    >
        <AppTable
        columns={columns}
        data={isLoading ? [] : resources}
        emptyMessage={emptyMessage}
        />
    </ScrollArea>
  )
}

export default UtilizationTable
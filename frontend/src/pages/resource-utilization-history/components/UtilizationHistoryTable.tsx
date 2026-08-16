import { Badge, ScrollArea } from '@mantine/core'

import AppTable, {
  type Column,
} from '../../../components/tables/AppTable'

import UtilizationProgress from '../../resource-utilization-report/components/UtilizationProgress'
import { UTILIZATION_STATUS_META } from '../../resource-utilization-report/utilizationStatus'

import type { UtilizationHistoryRow } from '../types'

interface UtilizationHistoryTableProps {
  rows: UtilizationHistoryRow[]
  isLoading: boolean
  isError: boolean
}

// Same status badges/progress bar as the current Resource Utilization
// Report's own UtilizationTable.tsx, so a history snapshot reads as
// "the same report, frozen at a point in time" rather than a
// different visual language (per utilizationStatus.ts's shared
// convention).
const UtilizationHistoryTable = ({
  rows,
  isLoading,
  isError,
}: UtilizationHistoryTableProps) => {
  const columns: Column<UtilizationHistoryRow>[] = [
    {
      accessor: 'utilizationNumber',
      title: 'Utilization ID',
    },
    {
      accessor: 'generatedAt',
      title: 'Date Generated',
    },
    {
      accessor: 'resourceName',
      title: 'Resource',
    },
    {
      accessor: 'consumedQuantity',
      title: 'Consumed',
      render: (row) => `${row.consumedQuantity} ${row.unit}`,
    },
    {
      accessor: 'remainingQuantity',
      title: 'Remaining',
      render: (row) => `${row.remainingQuantity} ${row.unit}`,
    },
    {
      accessor: 'utilizationPercent',
      title: 'Utilization %',
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
    ? 'Loading resource utilization history...'
    : isError
      ? 'Unable to load resource utilization history.'
      : 'No resource utilization history yet - apply a production plan to create the first snapshot.'

  return (
    <ScrollArea type="auto" offsetScrollbars>
      <AppTable
        columns={columns}
        data={isLoading ? [] : rows}
        emptyMessage={emptyMessage}
      />
    </ScrollArea>
  )
}

export default UtilizationHistoryTable

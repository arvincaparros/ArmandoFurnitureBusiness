import {
  Badge,
  Card,
  Text,
} from '@mantine/core'

import AppTable, {
  type Column,
} from '../../../components/tables/AppTable'

import {
  resolveUtilizationStatus,
  UTILIZATION_STATUS_META,
} from '../../resource-utilization-report/utilizationStatus'

import type { ResourceUtilizationRow } from '../types'

interface ResourceUtilizationSummaryCardProps {
  resourceUsage: ResourceUtilizationRow[]
}

// THIS Generate result's own proposed resource usage only - never
// blended with an earlier Generate's figures (see
// productionAdapter.ts::toResourceUtilizationRows and the backend's
// calculate_optimized_resource_usage, both of which compute this
// fresh per call). Deliberately a SEPARATE card from the
// Resource Utilization Reports page (/reports), which continues to
// show actual APPLIED consumption from the production ledger,
// unchanged - this card previews what THIS plan would consume, not
// what has actually been produced.
const ResourceUtilizationSummaryCard = ({
  resourceUsage,
}: ResourceUtilizationSummaryCardProps) => {
  if (resourceUsage.length === 0) {
    return null
  }

  const columns: Column<ResourceUtilizationRow>[] = [
    {
      accessor: 'resourceName',
      title: 'Resource',
    },
    {
      accessor: 'consumed',
      title: 'Consumed',
      render: (row) => `${row.consumed} ${row.unit}`,
    },
    {
      accessor: 'remaining',
      title: 'Remaining',
      render: (row) => `${row.remaining} ${row.unit}`,
    },
    {
      accessor: 'utilizationRate',
      title: 'Utilization',
      render: (row) => `${row.utilizationRate.toFixed(1)}%`,
    },
    {
      accessor: 'status',
      title: 'Status',
      textAlign: 'center',
      render: (row) => {
        const status = resolveUtilizationStatus(row.status)
        const meta = UTILIZATION_STATUS_META[status]

        return (
          <Badge
            color={meta.color}
            variant="light"
            size="sm"
          >
            {meta.label.toUpperCase()}
          </Badge>
        )
      },
    },
  ]

  return (
    <Card
      withBorder
      radius="md"
      p="lg"
    >
      <Text fw={600} mb="xs">
        Resource Utilization Summary
      </Text>

      <Text
        size="sm"
        c="dimmed"
        mb="md"
      >
        {resourceUsage.length} resource
        {resourceUsage.length !== 1 ? 's' : ''} - this plan's own
        proposed usage, not yet applied.
      </Text>

      <AppTable
        columns={columns}
        data={resourceUsage}
      />
    </Card>
  )
}

export default ResourceUtilizationSummaryCard

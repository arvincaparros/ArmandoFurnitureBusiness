import {
  Badge,
  Group,
  ScrollArea,
  Text,
  Tooltip,
} from '@mantine/core'
import AppTable, {
  type Column,
} from '../../../components/tables/AppTable'

import type { Resource } from '../types'

import ResourceRowActions from './ResourceRowActions'

const PRICING_UNAVAILABLE_MESSAGE =
  'Not yet configured for the current production cycle. Edit this resource to set it.'

const pricingCell = (
  value: number | null,
  format: (value: number) => string,
) =>
  value === null ? (
    <Tooltip label={PRICING_UNAVAILABLE_MESSAGE}>
      <span>—</span>
    </Tooltip>
  ) : (
    format(value)
  )

interface ResourceTableProps {
  resources: Resource[]
  onEdit: (resource: Resource) => void
  onDelete: (resource: Resource) => void
  onReactivate: (resource: Resource) => void

  isLoading: boolean
  isError: boolean
  emptyMessage: string

  sortBy: keyof Resource | string
  reverse: boolean
  onSort: (
    accessor: keyof Resource | string,
  ) => void
}

const ResourceTable = ({
  resources,
  onEdit,
  onDelete,
  onReactivate,
  isLoading,
  isError,
  emptyMessage,
  sortBy,
  reverse,
  onSort,
}: ResourceTableProps) => {

  const columns: Column<Resource>[] = [
    {
      accessor: 'name',
      title: 'Name',
      sortable: true,
      render: (row) => (
        <Group gap="xs" wrap="nowrap">
          <Text>{row.name}</Text>

          {!row.isActive && (
            <Badge
              color="gray"
              variant="light"
              size="sm"
            >
              Inactive
            </Badge>
          )}
        </Group>
      ),
    },
    {
      accessor: 'resourceType',
      title: 'Category',
      sortable: true,
      render: (row) => (
        <Badge variant="light" tt="capitalize">
          {row.resourceType}
        </Badge>
      ),
    },
    {
      accessor: 'unit',
      title: 'Unit',
      sortable: true,
    },
    {
      accessor: 'availableQuantity',
      title: 'Available Quantity',
      sortable: true,
      textAlign: 'right',
      render: (row) =>
        pricingCell(
          row.availableQuantity,
          (value) => `${value.toLocaleString()} ${row.unit}`,
        ),
    },
    {
      accessor: 'unitPrice',
      title: 'Unit Price',
      sortable: true,
      textAlign: 'right',
      render: (row) =>
        pricingCell(
          row.unitPrice,
          (value) => `₱${value.toLocaleString()} / ${row.unit}`,
        ),
    },
    {
      accessor: 'actions',
      title: 'Actions',
      textAlign: 'center',
      render: (row) => (
        <ResourceRowActions
            resource={row}
            onEdit={onEdit}
            onDelete={onDelete}
            onReactivate={onReactivate}
        />
      ),
    },
  ]

  const resolvedEmptyMessage = isLoading
    ? 'Loading resources...'
    : isError
      ? 'Unable to load resources.'
      : emptyMessage

  return (
    <ScrollArea
      type="auto"
      offsetScrollbars
    >
      <AppTable<Resource>
          columns={columns}
          data={isLoading ? [] : resources}
          sortBy={sortBy}
          reverse={reverse}
          onSort={onSort}
          emptyMessage={resolvedEmptyMessage}
      />
    </ScrollArea>
  )
}

export default ResourceTable

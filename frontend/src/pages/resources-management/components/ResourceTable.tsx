import { ScrollArea } from '@mantine/core'
import AppTable, {
  type Column,
} from '../../../components/tables/AppTable'

import type { Resource } from '../types'

import ResourceRowActions from './ResourceRowActions'

interface ResourceTableProps {
  resources: Resource[]
  onEdit: (resource: Resource) => void
  onDelete: (resource: Resource) => void

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
  sortBy,
  reverse,
  onSort,
}: ResourceTableProps) => {

  const columns: Column<Resource>[] = [
    {
      accessor: 'resourceType',
      title: 'Resource Type',
      sortable: true,
    },
    {
      accessor: 'availableQuantity',
      title: 'Available Quantity',
      sortable: true,
    },
    {
      accessor: 'unitPrice',
      title: 'Unit Price',
      sortable: true,
      render: (row) =>
        `₱${row.unitPrice.toFixed(2)}`,
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
        />
      ),
    },
  ]

  return (
    <ScrollArea
      type="auto"
      offsetScrollbars
    >
      <AppTable<Resource>
          columns={columns}
          data={resources}
          sortBy={sortBy}
          reverse={reverse}
          onSort={onSort}
          emptyMessage="No resources found."
      />
    </ScrollArea>
  )
}

export default ResourceTable
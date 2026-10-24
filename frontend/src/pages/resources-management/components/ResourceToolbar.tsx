import { Button, Group, SegmentedControl } from '@mantine/core'
import { Plus } from 'lucide-react'

import type { ResourceStatusFilter } from '../types'

interface ResourceToolbarProps {
  onAdd: () => void
  statusFilter: ResourceStatusFilter
  onStatusFilterChange: (value: ResourceStatusFilter) => void
  activeCount: number
  inactiveCount: number
}

const ResourceToolbar = ({
  onAdd,
  statusFilter,
  onStatusFilterChange,
  activeCount,
  inactiveCount,
}: ResourceToolbarProps) => {
  return (
    <Group justify="space-between" mb="md">
      <SegmentedControl
        value={statusFilter}
        onChange={(value) =>
          onStatusFilterChange(value as ResourceStatusFilter)
        }
        data={[
          { label: `Active (${activeCount})`, value: 'active' },
          { label: `Inactive (${inactiveCount})`, value: 'inactive' },
        ]}
      />

      <Button
        leftSection={<Plus size={18} />}
        onClick={onAdd}
      >
        Add Resource
      </Button>
    </Group>
  )
}

export default ResourceToolbar

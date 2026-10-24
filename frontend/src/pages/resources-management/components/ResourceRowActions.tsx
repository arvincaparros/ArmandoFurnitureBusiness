import { ActionIcon, Group } from '@mantine/core'

import {
  ArchiveRestore,
  Pencil,
  Trash2,
} from 'lucide-react'

import type { Resource } from '../types'

interface ResourceRowActionsProps {
  resource: Resource
  onEdit?: (resource: Resource) => void
  onDelete?: (resource: Resource) => void
  onReactivate?: (resource: Resource) => void
}

const ResourceRowActions = ({
  resource,
  onEdit,
  onDelete,
  onReactivate,
}: ResourceRowActionsProps) => {
  // Inactive rows are soft-deleted records that only support
  // reactivation (a PATCH of is_active on this same row). Editing a
  // catalog entry while it is inactive is deliberately not offered
  // here, and a second delete would be a no-op.
  if (!resource.isActive) {
    return (
      <Group
        justify="center"
        gap="xs"
        wrap="nowrap"
        w="100%"
      >
        <ActionIcon
          variant="subtle"
          color="green"
          aria-label={`Reactivate ${resource.name}`}
          onClick={() => onReactivate?.(resource)}
        >
          <ArchiveRestore size={16} />
        </ActionIcon>
      </Group>
    )
  }

  return (
    <Group
      justify="center"
      gap="xs"
      wrap="nowrap"
      w="100%"
    >
      <ActionIcon
        variant="subtle"
        color="blue"
        aria-label={`Edit ${resource.name}`}
        onClick={() => onEdit?.(resource)}
      >
        <Pencil size={16} />
      </ActionIcon>

      <ActionIcon
        variant="subtle"
        color="red"
        onClick={() => onDelete?.(resource)}
      >
        <Trash2 size={16} />
      </ActionIcon>
    </Group>
  )
}

export default ResourceRowActions
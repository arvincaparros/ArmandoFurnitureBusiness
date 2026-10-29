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
  onPermanentDelete?: (resource: Resource) => void
}

const ResourceRowActions = ({
  resource,
  onEdit,
  onDelete,
  onReactivate,
  onPermanentDelete,
}: ResourceRowActionsProps) => {
  // Inactive rows are soft-deleted records. They support
  // reactivation (a PATCH of is_active on this same row) and
  // permanent deletion (DELETE /{id}/permanent, which removes the
  // catalogue row outright) - two different endpoints, so the two
  // actions are deliberately kept visually distinct. Editing a
  // catalog entry while it is inactive is still not offered here,
  // and the soft-delete action is not repeated: a second
  // deactivation would be a no-op.
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

        <ActionIcon
          variant="subtle"
          color="red"
          aria-label={`Delete ${resource.name} permanently`}
          onClick={() => onPermanentDelete?.(resource)}
        >
          <Trash2 size={16} />
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
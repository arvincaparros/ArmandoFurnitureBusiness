import { ActionIcon, Group } from '@mantine/core'

import {
  Pencil,
  Trash2,
} from 'lucide-react'

import type { Resource } from '../types'

interface ResourceRowActionsProps {
  resource: Resource
  onEdit?: (resource: Resource) => void
  onDelete?: (resource: Resource) => void
}

const ResourceRowActions = ({
  resource,
  onEdit,
  onDelete,
}: ResourceRowActionsProps) => {
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
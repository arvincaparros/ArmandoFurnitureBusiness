import { ActionIcon, Group } from '@mantine/core'

import {
  Pencil,
  Trash2,
} from 'lucide-react'

import type { Transaction } from '../types'

interface TransactionRowActionsProps {
  transaction: Transaction
  onEdit?: (transaction: Transaction) => void
  onDelete?: (transaction: Transaction) => void
}

const TransactionRowActions = ({
  transaction,
  onEdit,
  onDelete,
}: TransactionRowActionsProps) => {
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
        onClick={() => onEdit?.(transaction)}
      >
        <Pencil size={16} />
      </ActionIcon>

      <ActionIcon
        variant="subtle"
        color="red"
        onClick={() => onDelete?.(transaction)}
      >
        <Trash2 size={16} />
      </ActionIcon>
    </Group>
  )
}

export default TransactionRowActions

import {
  ActionIcon,
  Group,
} from '@mantine/core'

import {
  Pencil,
  Trash2,
} from 'lucide-react'

import type { Product } from '../types'

interface ProductRowActionsProps {
  product: Product
  onEdit: (product: Product) => void
  onDelete: (product: Product) => void
}

const ProductRowActions = ({
  product,
  onEdit,
  onDelete,
}: ProductRowActionsProps) => {
  return (
    <Group
      justify="center"
      gap={6}
      wrap="nowrap"
    >
      <ActionIcon
        variant="subtle"
        color="blue"
        onClick={() => onEdit(product)}
      >
        <Pencil size={16} />
      </ActionIcon>

      <ActionIcon
        variant="subtle"
        color="red"
        onClick={() => onDelete(product)}
      >
        <Trash2 size={16} />
      </ActionIcon>
    </Group>
  )
}

export default ProductRowActions
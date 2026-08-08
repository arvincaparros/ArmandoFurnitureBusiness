import {
  Button,
  Group,
  Modal,
  Text,
} from '@mantine/core'

import type { Product } from '../types'

interface DeleteProductModalProps {
  opened: boolean
  onClose: () => void
  onConfirm: () => void
  product?: Product | null
}

const DeleteProductModal = ({
  opened,
  onClose,
  onConfirm,
  product,
}: DeleteProductModalProps) => {
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title="Delete Product"
      centered
    >
      <Text mb="md">
        Are you sure you want to delete{' '}
        <strong>
          {product?.productName ?? 'this product'}
        </strong>
        ?
      </Text>

      <Group justify="flex-end">
        <Button
          variant="default"
          onClick={onClose}
        >
          Cancel
        </Button>

        <Button
          color="red"
          onClick={onConfirm}
        >
          Delete
        </Button>
      </Group>
    </Modal>
  )
}

export default DeleteProductModal
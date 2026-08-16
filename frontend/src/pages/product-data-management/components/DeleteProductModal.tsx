import { useState } from 'react'

import {
  Alert,
  Button,
  Group,
  Modal,
  Text,
} from '@mantine/core'

import { AlertCircle } from 'lucide-react'

import { getApiErrorMessage } from '../../../api/apiError'

import type { Product } from '../types'

interface DeleteProductModalProps {
  opened: boolean
  onClose: () => void
  onConfirm: () => Promise<void>
  product?: Product | null
}

const DeleteProductModal = ({
  opened,
  onClose,
  onConfirm,
  product,
}: DeleteProductModalProps) => {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleConfirm = async () => {
    setIsSubmitting(true)
    setError(null)

    try {
      await onConfirm()
    } catch (deleteError) {
      setError(
        getApiErrorMessage(
          deleteError,
          'Unable to delete product. Please try again.',
        ),
      )
    } finally {
      setIsSubmitting(false)
    }
  }

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

      {error && (
        <Alert
          color="red"
          icon={<AlertCircle size={18} />}
          mb="md"
        >
          {error}
        </Alert>
      )}

      <Group justify="flex-end">
        <Button
          variant="default"
          onClick={onClose}
          disabled={isSubmitting}
        >
          Cancel
        </Button>

        <Button
          color="red"
          onClick={handleConfirm}
          loading={isSubmitting}
        >
          Delete
        </Button>
      </Group>
    </Modal>
  )
}

export default DeleteProductModal

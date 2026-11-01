import { useState } from 'react'

import {
  Alert,
  Button,
  Group,
  Modal,
  Text,
} from '@mantine/core'

import { AlertTriangle } from 'lucide-react'

import { getApiErrorMessage } from '../../../api/apiError'

interface ReviewConfirmModalProps {
  opened: boolean
  onClose: () => void
  onConfirm: () => Promise<unknown>
}

// Structural mirror of
// production-allocation/components/ApplyConfirmModal.tsx - same
// Alert, same getApiErrorMessage handling, same isSubmitting guard.
// The error branch matters more here than there: reviewing an
// INCOMPLETE set is refused by the backend with a 400 naming every
// product that still has no declared quantity, and that message is
// what the user needs to act on.
const ReviewConfirmModal = ({
  opened,
  onClose,
  onConfirm,
}: ReviewConfirmModalProps) => {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleConfirm = async () => {
    setIsSubmitting(true)
    setError(null)

    try {
      await onConfirm()
      onClose()
    } catch (reviewError) {
      setError(
        getApiErrorMessage(
          reviewError,
          'Unable to mark this opening inventory as reviewed. '
            + 'Please try again.',
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
      title="Mark as reviewed"
      centered
      size="sm"
    >
      <Text mb="md">
        Mark this opening inventory as reviewed?
      </Text>

      <Alert
        color="orange"
        variant="light"
        icon={<AlertTriangle size={18} />}
        mb="md"
      >
        These balances become the authoritative starting point for
        every stock figure, and stock-based validation of sales
        switches on. A reviewed set cannot be edited afterwards —
        correcting it means creating a new set.
      </Alert>

      {error && (
        <Alert
          color="red"
          icon={<AlertTriangle size={18} />}
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
          onClick={handleConfirm}
          loading={isSubmitting}
        >
          Confirm review
        </Button>
      </Group>
    </Modal>
  )
}

export default ReviewConfirmModal

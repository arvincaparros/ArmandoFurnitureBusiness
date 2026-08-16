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

interface ApplyConfirmModalProps {
  opened: boolean
  onClose: () => void
  onConfirm: () => Promise<unknown>
}

const ApplyConfirmModal = ({
  opened,
  onClose,
  onConfirm,
}: ApplyConfirmModalProps) => {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleConfirm = async () => {
    setIsSubmitting(true)
    setError(null)

    try {
      await onConfirm()
      onClose()
    } catch (applyError) {
      setError(
        getApiErrorMessage(
          applyError,
          'Unable to apply the production plan. Please try again.',
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
      title="Apply to Production"
      centered
      size="sm"
    >
      <Text mb="md">
        Apply this production plan?
      </Text>

      <Alert
        color="orange"
        variant="light"
        icon={<AlertTriangle size={18} />}
        mb="md"
      >
        This will replace the current committed allocation for
        this production cycle with the latest optimal plan.
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
          Apply to Production
        </Button>
      </Group>
    </Modal>
  )
}

export default ApplyConfirmModal

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

  // Units this plan will ADD, and what the cycle has already had
  // applied. Production is append-only now, so the copy has to say
  // "add" rather than the old "replace".
  plannedTotal: number
  cycleProducedTotal: number

  onClose: () => void
  onConfirm: () => Promise<unknown>
}

const ApplyConfirmModal = ({
  opened,
  plannedTotal,
  cycleProducedTotal,
  onClose,
  onConfirm,
}: ApplyConfirmModalProps) => {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const additiveMessage =
    `This will add ${plannedTotal} units to this cycle`
    + (cycleProducedTotal > 0
      ? `, on top of the ${cycleProducedTotal} units already applied`
      : '')
    + ', and consume the matching resource capacity.'
    + ' Previously applied production is never overwritten.'

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
        color="blue"
        variant="light"
        icon={<AlertTriangle size={18} />}
        mb="md"
      >
        {additiveMessage}
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

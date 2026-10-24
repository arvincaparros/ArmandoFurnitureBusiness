import { useState } from 'react'

import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Modal,
  Stack,
  Text,
} from '@mantine/core'

import {
  AlertTriangle,
  ArchiveRestore,
  Package,
} from 'lucide-react'

import { getApiErrorMessage } from '../../../api/apiError'

import type { Resource } from '../types'

interface ReactivateResourceModalProps {
  opened: boolean
  resource: Resource | null
  onClose: () => void
  onConfirm: () => Promise<void>
}

const ReactivateResourceModal = ({
  opened,
  resource,
  onClose,
  onConfirm,
}: ReactivateResourceModalProps) => {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleClose = () => {
    if (isSubmitting) return

    setError(null)
    onClose()
  }

  const handleConfirm = async () => {
    if (isSubmitting) return

    setIsSubmitting(true)
    setError(null)

    try {
      await onConfirm()
    } catch (reactivateError) {
      setError(
        getApiErrorMessage(
          reactivateError,
          'Unable to reactivate resource. Please try again.',
        ),
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Modal
      opened={opened}
      onClose={handleClose}
      title="Reactivate Resource"
      centered
      size="sm"
    >
      <Stack gap="lg">
        <Alert
          color="green"
          variant="light"
          icon={<ArchiveRestore size={18} />}
        >
          This resource will become available again for products and
          production cycles. Its ID, category, unit, and existing
          product-resource requirements are kept. Production-cycle
          quantities and prices are not changed.
        </Alert>

        <Card withBorder radius="md">
          <Group justify="space-between">
            <Group>
              <Package size={18} />

              <Stack gap={2}>
                <Text fw={600}>
                  {resource?.name}
                </Text>

                <Text size="sm" c="dimmed">
                  {resource?.resourceType} • {resource?.unit}
                </Text>
              </Stack>
            </Group>

            <Badge color="gray" variant="light">
              {resource?.isActive ? 'Active' : 'Inactive'}
            </Badge>
          </Group>
        </Card>

        {error && (
          <Alert
            color="red"
            icon={<AlertTriangle size={18} />}
          >
            {error}
          </Alert>
        )}

        <Group justify="flex-end">
          <Button
            variant="default"
            onClick={handleClose}
            disabled={isSubmitting}
          >
            Cancel
          </Button>

          <Button
            color="green"
            leftSection={<ArchiveRestore size={16} />}
            onClick={handleConfirm}
            loading={isSubmitting}
          >
            Reactivate Resource
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

export default ReactivateResourceModal

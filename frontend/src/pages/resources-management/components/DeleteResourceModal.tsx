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
  Package,
} from 'lucide-react'

import { getApiErrorMessage } from '../../../api/apiError'

import type { Resource } from '../types'

interface DeleteResourceModalProps {
  opened: boolean
  resource: Resource | null
  onClose: () => void
  onConfirm: () => Promise<void>
}

const DeleteResourceModal = ({
  opened,
  resource,
  onClose,
  onConfirm,
}: DeleteResourceModalProps) => {
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
          'Unable to delete resource. Please try again.',
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
      title="Delete Resource"
      centered
      size="sm"
    >
      <Stack gap="lg">
        <Alert
            color="red"
            variant="light"
            icon={<AlertTriangle size={18} />}
        >
            This action cannot be undone.
        </Alert>

        <Card
            withBorder
            radius="md"
        >
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
                onClick={onClose}
                disabled={isSubmitting}
            >
                Cancel
            </Button>

            <Button
                color="red"
                leftSection={<AlertTriangle size={16} />}
                onClick={handleConfirm}
                loading={isSubmitting}
            >
                Delete Resource
            </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

export default DeleteResourceModal

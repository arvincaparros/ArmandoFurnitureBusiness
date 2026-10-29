import { useState } from 'react'

import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  List,
  Modal,
  Stack,
  Text,
} from '@mantine/core'

import {
  AlertTriangle,
  Package,
  Trash2,
} from 'lucide-react'

import { getApiErrorMessage } from '../../../api/apiError'

import type { Resource } from '../types'

interface PermanentDeleteResourceModalProps {
  opened: boolean
  resource: Resource | null
  onClose: () => void
  onConfirm: () => Promise<void>
}

// Separate from DeleteResourceModal, which confirms the reversible
// soft delete of an ACTIVE resource ("existing records are kept, its
// name stays reserved"). This one confirms the irreversible removal
// of an already-inactive row, so it has to say the opposite about
// both of those things.
const PermanentDeleteResourceModal = ({
  opened,
  resource,
  onClose,
  onConfirm,
}: PermanentDeleteResourceModalProps) => {
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
    } catch (deleteError) {
      // A 409 carries the backend's specific reason as its detail -
      // which product requirements or production cycles still
      // reference this resource - and getApiErrorMessage surfaces
      // that string as-is. The fallback only applies when the error
      // has no usable detail at all, so a blocked delete always
      // tells the user what to clear rather than just that it
      // failed. The modal deliberately stays open on failure.
      setError(
        getApiErrorMessage(
          deleteError,
          'Unable to delete this resource permanently. Please try again.',
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
      title="Delete Resource Permanently"
      centered
      size="md"
    >
      <Stack gap="lg">
        <Alert
          color="red"
          variant="light"
          icon={<AlertTriangle size={18} />}
          title="This cannot be undone"
        >
          <Stack gap="xs">
            <Text size="sm">
              {resource?.name
                ? `${resource.name} will be removed from the resource catalog for good.`
                : 'This resource will be removed from the resource catalog for good.'}
              {' '}
              It cannot be reactivated afterwards.
            </Text>

            <List size="sm" spacing={4}>
              <List.Item>
                Its name becomes available again, so a new
                resource can reuse it.
              </List.Item>

              <List.Item>
                Resource utilization history is kept and stays
                readable.
              </List.Item>

              <List.Item>
                If any product requirement or production cycle
                still uses it, the deletion is refused and nothing
                is changed.
              </List.Item>
            </List>
          </Stack>
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
            title="Deletion blocked"
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
            color="red"
            leftSection={<Trash2 size={16} />}
            onClick={handleConfirm}
            loading={isSubmitting}
          >
            Delete Permanently
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

export default PermanentDeleteResourceModal

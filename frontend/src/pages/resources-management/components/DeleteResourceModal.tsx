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

import type { Resource } from '../types'

interface DeleteResourceModalProps {
  opened: boolean
  resource: Resource | null
  onClose: () => void
  onConfirm: () => void
}

const DeleteResourceModal = ({
  opened,
  resource,
  onClose,
  onConfirm,
}: DeleteResourceModalProps) => {
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
                    {resource?.resourceType}
                </Text>

                <Text size="sm" c="dimmed">
                    Qty: {resource?.availableQuantity} {resource?.unit}
                </Text>
                </Stack>
            </Group>

            <Badge color="green" variant="light">
                ₱{resource?.unitPrice.toFixed(2)}
            </Badge>
            </Group>
        </Card>

        <Group justify="flex-end">
            <Button
                variant="default"
                onClick={onClose}
            >
                Cancel
            </Button>

            <Button
                color="red"
                leftSection={<AlertTriangle size={16} />}
                onClick={onConfirm}
            >
                Delete Resource
            </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

export default DeleteResourceModal
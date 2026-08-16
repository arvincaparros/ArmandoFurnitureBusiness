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
  Receipt,
} from 'lucide-react'

import { getApiErrorMessage } from '../../../api/apiError'

import type { Transaction } from '../types'

interface DeleteTransactionModalProps {
  opened: boolean
  transaction: Transaction | null
  onClose: () => void
  onConfirm: () => Promise<void>
}

// Stronger warning than DeleteResourceModal/DeleteProductModal on
// purpose: those soft-delete (is_active = false, reversible by an
// admin), this is a genuine hard DELETE
// (app/services/transaction.py::delete_transaction) with no
// undo/reactivate path anywhere in the backend contract - and unlike
// Resources/Products, a transaction directly feeds Demand
// Forecasting's live historical-demand calculation, so removing one
// changes real forecast output.
const DeleteTransactionModal = ({
  opened,
  transaction,
  onClose,
  onConfirm,
}: DeleteTransactionModalProps) => {
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
          'Unable to delete transaction. Please try again.',
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
      title="Delete Transaction"
      centered
      size="sm"
    >
      <Stack gap="lg">
        <Alert
            color="red"
            variant="filled"
            icon={<AlertTriangle size={18} />}
        >
            This deletion is permanent and cannot be undone - unlike
            Resources or Products, this transaction record is removed
            entirely, not deactivated, and there is no way to recover
            it afterward. Deleting it will also change this product&apos;s
            historical demand figures the next time Demand Forecasting
            is viewed.
        </Alert>

        <Card
            withBorder
            radius="md"
        >
            <Group justify="space-between">
            <Group>
                <Receipt size={18} />

                <Stack gap={2}>
                <Text fw={600}>
                    {transaction?.transactionNumber}
                </Text>

                <Text size="sm" c="dimmed">
                    {transaction?.furnitureProduct} • {transaction?.date}
                </Text>
                </Stack>
            </Group>

            <Badge color="gray" variant="light">
                ₱{transaction?.profitEarned.toLocaleString()}
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
                Delete Permanently
            </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

export default DeleteTransactionModal

import { useEffect, useState } from 'react'

import {
  Alert,
  Button,
  Card,
  Divider,
  Group,
  Modal,
  NumberInput,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
} from '@mantine/core'

import { AlertCircle, Lock } from 'lucide-react'

import { getApiErrorMessage } from '../../../api/apiError'

import type { Transaction } from '../types'
import type {
  ProductSummary,
  SalesTransactionCreateRequest,
  SalesTransactionUpdateRequest,
} from '../api/transactionTypes'

// Same Decimal-as-JSON-string convention as transactionAdapter.ts's
// parseDecimal - duplicated locally rather than imported, matching
// this codebase's per-module convention.
function parseDecimal(value: string): number {
  const parsed = Number(value)

  return Number.isFinite(parsed) ? parsed : 0
}

interface AddTransactionModalProps {
  opened: boolean
  products: ProductSummary[]
  transaction?: Transaction | null

  // product_id -> available stock across all cycles (opening + all
  // applied production - all sales, continuous, never reset). Drives
  // both the Quantity Produced display below and the Quantity Sold
  // max/validation. Comes from GET /api/inventory via useTransactions.
  stockByProductId: Record<number, number>
  // product_id -> this cycle's unclaimed applied production. Kept in
  // the prop shape for compatibility with the caller (TransactionHistoryPage.tsx
  // still passes it, used by nothing else there) - deliberately unused
  // in this component: it is a per-cycle drawdown, not available
  // stock, and using it for the Quantity Produced display was the bug
  // this field's binding below was changed to fix.
  producedByProductId: Record<number, number>
  isStockValidationEnabled: boolean

  onClose: () => void
  onSave: (
    data:
      | SalesTransactionCreateRequest
      | SalesTransactionUpdateRequest,
  ) => Promise<void>
}

// transaction_number is server-generated (see transactionTypes.ts) -
// there is no input for it here, unlike the old mock form. Sales
// Amount is likewise not collected directly: the backend computes
// total_sales as quantity (sold) * unit_price, so Unit Price is the
// real per-unit input and the Transaction Summary card below is a
// read-only client preview of that total - the table always displays
// the authoritative value from the API response, not this preview.
//
// Production Cost / Unit is no longer collected here. The create
// contract still requires it (app/schemas/transaction.py::
// SalesTransactionCreate), so new transactions are submitted at 0;
// edits omit it entirely so the backend reconstructs and preserves
// the per-unit rate a transaction was saved with
// (app/services/transaction.py::update_transaction).
//
// Edit mode (transaction prop set): the Product select is locked -
// SalesTransactionUpdateRequest has no product_id field at all, the
// backend does not allow reassigning a transaction to a different
// product after creation (verified server-side too: a product_id
// sent via PATCH is silently ignored, confirmed live during the
// Edit/Delete implementation).
const AddTransactionModal = ({
  opened,
  products,
  transaction,
  stockByProductId,
  isStockValidationEnabled,
  onClose,
  onSave,
}: AddTransactionModalProps) => {
  const isEditMode = transaction != null

  const [productId, setProductId] = useState<
    number | null
  >(null)

  const [date, setDate] = useState('')

  const [quantitySold, setQuantitySold] =
    useState(0)

  const [unitPrice, setUnitPrice] = useState(0)

  const [isSubmitting, setIsSubmitting] =
    useState(false)

  const [error, setError] = useState<
    string | null
  >(null)

  useEffect(() => {
    if (transaction) {
      setProductId(transaction.productId)
      setDate(transaction.date)
      setQuantitySold(transaction.quantitySold)
      setUnitPrice(transaction.unitPrice)
    } else {
      setProductId(null)
      setDate(
        new Date().toISOString().split('T')[0],
      )
      setQuantitySold(0)
      setUnitPrice(0)
    }

    setError(null)
  }, [transaction, opened])

  // Displays the product's current available production balance
  // (opening + all applied production - all sales, continuous,
  // never reset - see services/inventory.py::get_available_stock) -
  // NOT producedByProductId's per-cycle drawdown, which is a
  // different figure that resets at a cycle boundary and drains as
  // sales attribute against it. This field is purely a display
  // preview: quantity_produced is never sent in the create/update
  // request (see handleSave below), so this has no effect on what
  // the backend actually records. In edit mode the stored value is
  // shown as-is, unchanged from before.
  const displayedQuantityProduced = isEditMode
    ? (transaction?.quantityProduced ?? 0)
    : productId !== null
      ? (stockByProductId[productId] ?? 0)
      : 0

  const availableStock =
    productId !== null
      ? (stockByProductId[productId] ?? 0)
      : 0

  const exceedsStock =
    isStockValidationEnabled &&
    !isEditMode &&
    productId !== null &&
    quantitySold > availableStock

  // Sales revenue is earned on units SOLD (matches
  // app/services/transaction.py::calculate_transaction_values).
  const estimatedSales = quantitySold * unitPrice

  // quantityProduced > 0 is gone: it is no longer user-controlled,
  // and 0 is a legitimate value for the second sale in a cycle.
  const isValid =
    productId !== null &&
    date.trim() !== '' &&
    quantitySold > 0 &&
    unitPrice > 0 &&
    !exceedsStock

  const handleSave = async () => {
    if (!isValid || isSubmitting) {
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      if (isEditMode) {
        // production_cost is deliberately omitted: the backend
        // reconstructs the per-unit rate from the stored total
        // (app/services/transaction.py::update_transaction), so a
        // transaction keeps the cost it was saved with instead of
        // being reset to zero.
        await onSave({
          transaction_date: `${date}T00:00:00`,
          quantity: quantitySold,
          unit_price: unitPrice,
        })
      } else {
        // The create contract still requires a per-unit production
        // cost and this form no longer collects one, so new
        // transactions are recorded at 0. Existing records are not
        // touched.
        await onSave({
          product_id: productId as number,
          transaction_date: `${date}T00:00:00`,
          quantity: quantitySold,
          unit_price: unitPrice,
          production_cost: 0,
        })
      }

      onClose()
    } catch (submitError) {
      setError(
        getApiErrorMessage(
          submitError,
          'Unable to save transaction. Please try again.',
        ),
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  const productOptions = products.map(
    (product) => ({
      value: String(product.id),
      label: product.name,
    }),
  )

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        isEditMode
          ? 'Edit Transaction'
          : 'Add Transaction'
      }
      centered
      size="lg"
      radius="lg"
      styles={{
        content: {
        borderRadius: 16,
        overflow: 'hidden',
        },
      }}
    >
      <Stack gap="xs">
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <TextInput
            radius="md"
            label="Date"
            type="date"
            value={date}
            onChange={(e) =>
              setDate(
                e.currentTarget.value,
              )
            }
          />

          <Select
            radius="md"
            label="Furniture Product"
            placeholder="Select a product"
            data={productOptions}
            value={
              productId !== null
                ? String(productId)
                : null
            }
            onChange={(value) => {
              const nextProductId = value
                ? Number(value)
                : null

              setProductId(nextProductId)

              // Auto-fill Unit Price from the product's existing
              // Selling Price (Product Data Management's own
              // selling_price, reused as-is - never hardcoded).
              // Stays editable afterward, same as every other field
              // here - only the product itself is locked, and only
              // in edit mode.
              const selectedProduct = products.find(
                (product) => product.id === nextProductId,
              )

              setUnitPrice(
                selectedProduct
                  ? parseDecimal(
                      selectedProduct.selling_price,
                    )
                  : 0,
              )
            }}
            searchable
            disabled={isEditMode}
            rightSection={
              isEditMode ? <Lock size={14} /> : undefined
            }
            description={
              isEditMode
                ? 'Product cannot be changed after a transaction is created.'
                : undefined
            }
          />
        </SimpleGrid>

        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <NumberInput
            radius="md"
            label="Quantity Produced"
            value={displayedQuantityProduced}
            readOnly
            description="Filled automatically from applied production"
          />

          <NumberInput
            radius="md"
            label="Quantity Sold"
            value={quantitySold}
            onChange={(value) =>
              setQuantitySold(
                Number(value),
              )
            }
            min={0}
            max={
              isStockValidationEnabled && !isEditMode
                ? availableStock
                : undefined
            }
            error={
              exceedsStock
                ? `Only ${availableStock} units are available`
                : undefined
            }
            description={
              isStockValidationEnabled && productId !== null
                ? `${availableStock} units available`
                : undefined
            }
          />
        </SimpleGrid>

        <NumberInput
          radius="md"
          label="Unit Price"
          prefix="₱ "
          value={unitPrice}
          onChange={(value) =>
            setUnitPrice(Number(value))
          }
          min={0}
        />

        <Divider
          my={4}
          label="Transaction Summary"
          labelPosition="center"
        />

        <Card
          withBorder
          radius="md"
          padding="sm"
        >
          <Stack gap={6}>
            <Group justify="space-between">
              <Text size="sm" c="dimmed">
                Estimated Sales Amount
              </Text>

              <Text size="sm" fw={600}>
                ₱{estimatedSales.toLocaleString()}
              </Text>
            </Group>
          </Stack>
        </Card>

        {error && (
          <Alert
            color="red"
            icon={<AlertCircle size={18} />}
          >
            {error}
          </Alert>
        )}

        <Group justify="flex-end" mt={4}>
          <Button
            variant="default"
            onClick={onClose}
            disabled={isSubmitting}
          >
            Cancel
          </Button>

          <Button
            onClick={handleSave}
            disabled={!isValid}
            loading={isSubmitting}
          >
            Save
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

export default AddTransactionModal

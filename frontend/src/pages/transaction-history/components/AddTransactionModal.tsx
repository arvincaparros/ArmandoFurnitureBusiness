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
// total_sales as quantity (sold) * unit_price, and the stored/
// returned production_cost as quantity_produced * "Production Cost /
// Unit" (app/services/transaction.py::calculate_transaction_values) -
// so Unit Price and Production Cost / Unit are the real per-unit
// inputs, and the Transaction Summary card below is a read-only
// client preview of what the backend will compute - the table always
// displays the authoritative value from the API response, not this
// preview.
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
  onClose,
  onSave,
}: AddTransactionModalProps) => {
  const isEditMode = transaction != null

  const [productId, setProductId] = useState<
    number | null
  >(null)

  const [date, setDate] = useState('')

  const [
    quantityProduced,
    setQuantityProduced,
  ] = useState(0)

  const [quantitySold, setQuantitySold] =
    useState(0)

  const [unitPrice, setUnitPrice] = useState(0)

  const [
    productionCost,
    setProductionCost,
  ] = useState(0)

  const [isSubmitting, setIsSubmitting] =
    useState(false)

  const [error, setError] = useState<
    string | null
  >(null)

  useEffect(() => {
    if (transaction) {
      setProductId(transaction.productId)
      setDate(transaction.date)
      setQuantityProduced(
        transaction.quantityProduced,
      )
      setQuantitySold(transaction.quantitySold)
      setUnitPrice(transaction.unitPrice)
      // transaction.productionCost is the stored TOTAL (Quantity
      // Produced x per-unit rate - see app/schemas/transaction.py's
      // SalesTransactionResponse.production_cost). This field is
      // per-unit, so it's reconstructed the same way the backend
      // reconstructs it when a PATCH omits production_cost
      // (app/services/transaction.py::update_transaction) - dividing
      // back by the quantity that produced it, not the raw total.
      setProductionCost(
        transaction.quantityProduced > 0
          ? transaction.productionCost /
              transaction.quantityProduced
          : 0,
      )
    } else {
      setProductId(null)
      setDate(
        new Date().toISOString().split('T')[0],
      )
      setQuantityProduced(0)
      setQuantitySold(0)
      setUnitPrice(0)
      setProductionCost(0)
    }

    setError(null)
  }, [transaction, opened])

  // Sales revenue is earned on units SOLD; production cost is
  // incurred on units PRODUCED - these use different quantities on
  // purpose (matches app/services/transaction.py::
  // calculate_transaction_values exactly).
  const estimatedSales = quantitySold * unitPrice
  const estimatedProductionCost =
    quantityProduced * productionCost
  const estimatedProfit =
    estimatedSales - estimatedProductionCost

  const isValid =
    productId !== null &&
    date.trim() !== '' &&
    quantityProduced > 0 &&
    quantitySold > 0 &&
    unitPrice > 0 &&
    productionCost >= 0

  const handleSave = async () => {
    if (!isValid || isSubmitting) {
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      if (isEditMode) {
        await onSave({
          transaction_date: `${date}T00:00:00`,
          quantity_produced: quantityProduced,
          quantity: quantitySold,
          unit_price: unitPrice,
          production_cost: productionCost,
        })
      } else {
        await onSave({
          product_id: productId as number,
          transaction_date: `${date}T00:00:00`,
          quantity_produced: quantityProduced,
          quantity: quantitySold,
          unit_price: unitPrice,
          production_cost: productionCost,
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
        <SimpleGrid cols={2}>
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

        <SimpleGrid cols={2}>
          <NumberInput
            radius="md"
            label="Quantity Produced"
            value={quantityProduced}
            onChange={(value) =>
              setQuantityProduced(
                Number(value),
              )
            }
            min={0}
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
          />
        </SimpleGrid>

        <SimpleGrid cols={2}>
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

          <NumberInput
            radius="md"
            label="Production Cost / Unit"
            prefix="₱ "
            value={productionCost}
            onChange={(value) =>
              setProductionCost(
                Number(value),
              )
            }
            min={0}
          />
        </SimpleGrid>

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

            <Group justify="space-between">
              <Text size="sm" c="dimmed">
                Estimated Production Cost
              </Text>

              <Text size="sm" fw={600}>
                ₱{estimatedProductionCost.toLocaleString()}
              </Text>
            </Group>

            <Group justify="space-between">
              <Text size="sm" c="dimmed">
                Estimated Profit
              </Text>

              <Text
                size="sm"
                fw={600}
                style={{
                  color:
                    estimatedProfit >= 0
                      ? '#16a34a'
                      : '#dc2626',
                }}
              >
                ₱{estimatedProfit.toLocaleString()}
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

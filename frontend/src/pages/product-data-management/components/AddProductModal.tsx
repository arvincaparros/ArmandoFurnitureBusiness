import { useEffect, useState } from 'react'

import {
  Alert,
  Button,
  Group,
  Modal,
  NumberInput,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
} from '@mantine/core'

import { AlertCircle } from 'lucide-react'

import { getApiErrorMessage } from '../../../api/apiError'

import ProductResourceRequirementsSection from './ProductResourceRequirementsSection'

import type { Product } from '../types'
import type {
  ProductCreateRequest,
  ProductUpdateRequest,
} from '../api/productTypes'

// Matches the backend's own bounds exactly (schemas/product.py::
// MinimumDemand) so the UI rejects what the API would 422 on, rather
// than relying on the error path for ordinary input.
const MINIMUM_DEMAND_MAX = 1_000_000

interface AddProductModalProps {
  opened: boolean
  onClose: () => void
  onSave: (
    data: ProductCreateRequest | ProductUpdateRequest,
  ) => Promise<void>
  product?: Product | null
}

const AddProductModal = ({
  opened,
  onClose,
  onSave,
  product,
}: AddProductModalProps) => {
  const [productName, setProductName] = useState('')
  const [sellingPrice, setSellingPrice] = useState(0)
  const [laborCost, setLaborCost] = useState(0)
  // Held as the raw NumberInput value (number, or '' once cleared)
  // rather than being funnelled through Number() on every keystroke:
  // Number('') is 0, and 0 is a REAL value here ("no minimum", which
  // drops the product out of the optimizer's positive-minimum
  // partition). Coercing an empty field to 0 would silently save that
  // meaning; keeping '' lets it be treated as invalid instead.
  const [minimumDemand, setMinimumDemand] = useState<
    number | string
  >(0)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (product) {
      setProductName(product.productName)
      setSellingPrice(product.sellingPrice)
      setLaborCost(product.laborCost ?? 0)
      // No `?? 0` fallback needed, unlike laborCost above: Product
      // .minimumDemand is a plain number that is never null, so the
      // real stored value always prefills - including a genuine 0.
      setMinimumDemand(product.minimumDemand)
    } else {
      setProductName('')
      setSellingPrice(0)
      setLaborCost(0)
      setMinimumDemand(0)
    }

    setError(null)
  }, [product, opened])

  const minimumDemandValue = Number(minimumDemand)

  // Mirrors schemas/product.py::MinimumDemand exactly: whole units,
  // nonnegative, at most MINIMUM_DEMAND_MAX. The explicit '' check is
  // what makes a cleared field block submission rather than being
  // read as 0; the Number.isInteger check additionally rejects any
  // NaN/fractional value that could reach the state.
  const isMinimumDemandValid =
    minimumDemand !== '' &&
    Number.isInteger(minimumDemandValue) &&
    minimumDemandValue >= 0 &&
    minimumDemandValue <= MINIMUM_DEMAND_MAX

  const isValid =
    productName.trim() !== '' &&
    sellingPrice > 0 &&
    laborCost >= 0 &&
    isMinimumDemandValid

  const handleSave = async () => {
    if (!isValid || isSubmitting) {
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      await onSave({
        name: productName,
        selling_price: sellingPrice,
        labor_cost: laborCost,
        minimum_demand: minimumDemandValue,
      })
    } catch (submitError) {
      setError(
        getApiErrorMessage(
          submitError,
          'Unable to save product. Please try again.',
        ),
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Modal.Root
      opened={opened}
      onClose={onClose}
      size="xl"
      centered
      radius="lg"
    >
      <Modal.Overlay />

      {/* Content is a fixed-height flex column (bounded by Mantine's
          own --modal-content-max-height, i.e. viewport-aware) with its
          own overflow hidden - Header and the action footer are fixed
          flex items, and only Body (flex: 1, its own overflow-y: auto)
          scrolls. This is what keeps the header/close button and
          Save/Cancel always reachable no matter how many resource
          requirement rows a product has. */}
      <Modal.Content
        style={{
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <Modal.Header>
          <Modal.Title>
            {product ? 'Edit Product' : 'Add Product'}
          </Modal.Title>

          <Modal.CloseButton />
        </Modal.Header>

        <Modal.Body
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            overflowX: 'hidden',
          }}
        >
          <Stack gap="xs">
            <SimpleGrid cols={2}>
              <TextInput
                radius="md"
                label="Product Name"
                placeholder="e.g. Dining Table"
                value={productName}
                maxLength={150}
                onChange={(e) =>
                  setProductName(e.currentTarget.value)
                }
              />

              <NumberInput
                radius="md"
                label="Selling Price"
                value={sellingPrice}
                prefix="₱"
                thousandSeparator=","
                onChange={(value) =>
                  setSellingPrice(Number(value))
                }
              />

              <NumberInput
                radius="md"
                label="Labor Cost"
                description="Per-unit labor cost - not derived from labor hours."
                value={laborCost}
                min={0}
                prefix="₱"
                thousandSeparator=","
                onChange={(value) =>
                  setLaborCost(Number(value))
                }
              />

              {/* A unit count, not currency - no ₱ prefix, and whole
                  units only (the backend rejects fractions with a
                  422, see schemas/product.py::_require_whole_units). */}
              <NumberInput
                radius="md"
                label="Minimum Demand"
                description="Minimum units the optimizer must produce per production cycle. 0 means no minimum."
                value={minimumDemand}
                min={0}
                max={MINIMUM_DEMAND_MAX}
                step={1}
                allowDecimal={false}
                allowNegative={false}
                thousandSeparator=","
                onChange={setMinimumDemand}
              />
            </SimpleGrid>

            {error && (
              <Alert
                color="red"
                icon={<AlertCircle size={18} />}
              >
                {error}
              </Alert>
            )}

            {product ? (
              <ProductResourceRequirementsSection
                productId={product.id}
              />
            ) : (
              <Text size="xs" c="dimmed" ta="center" mt="xs">
                Save the product first to add resource
                requirements.
              </Text>
            )}
          </Stack>
        </Modal.Body>

        <Group
          justify="flex-end"
          p="md"
          style={{
            flexShrink: 0,
            borderTop: '1px solid var(--mantine-color-default-border)',
          }}
        >
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
            {product
              ? 'Save Changes'
              : 'Add Product'}
          </Button>
        </Group>
      </Modal.Content>
    </Modal.Root>
  )
}

export default AddProductModal

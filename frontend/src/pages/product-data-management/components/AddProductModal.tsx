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

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (product) {
      setProductName(product.productName)
      setSellingPrice(product.sellingPrice)
      setLaborCost(product.laborCost ?? 0)
    } else {
      setProductName('')
      setSellingPrice(0)
      setLaborCost(0)
    }

    setError(null)
  }, [product, opened])

  const isValid =
    productName.trim() !== '' &&
    sellingPrice > 0 &&
    laborCost >= 0

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

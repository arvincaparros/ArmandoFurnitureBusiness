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

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (product) {
      setProductName(product.productName)
      setSellingPrice(product.sellingPrice)
    } else {
      setProductName('')
      setSellingPrice(0)
    }

    setError(null)
  }, [product, opened])

  const isValid =
    productName.trim() !== '' && sellingPrice > 0

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
    <Modal
        opened={opened}
        onClose={onClose}
        title={product ? 'Edit Product' : 'Add Product'}
        size="xl"
        centered
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

        <Group
            justify="flex-end"
            mt="md"
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
        </Stack>
    </Modal>
  )
}

export default AddProductModal

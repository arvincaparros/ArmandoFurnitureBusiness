import { useEffect, useState } from 'react'

import {
  Alert,
  Button,
  Group,
  Modal,
  NumberInput,
  Select,
  SimpleGrid,
  Stack,
  TextInput,
} from '@mantine/core'

import { AlertCircle } from 'lucide-react'

import { getApiErrorMessage } from '../../../api/apiError'

import type { Resource } from '../types'
import type {
  ResourceCreateRequest,
  ResourceUpdateRequest,
} from '../api/resourceTypes'

interface ResourcePricing {
  available_quantity: number
  unit_price: number
}

interface AddResourceModalProps {
  opened: boolean
  onClose: () => void
  onSave: (
    data: ResourceCreateRequest | ResourceUpdateRequest,
    pricing: ResourcePricing | null,
  ) => Promise<void>
  resource?: Resource | null
  // Availability/price (CycleResource) can only be saved once a
  // production cycle exists - see useResources.ts. When false, the
  // fields below are disabled rather than left to fail on submit.
  hasCycle: boolean
}

const units = [
  'board ft',
  'liter',
  'kg',
  'pcs',
  'hrs',
  'set',
].map((value) => ({
  value,
  label: value,
}))

// Matches backend/app/services/resource_utilization.py's
// _classify_resource_type() - "labor"/"machine" are recognized
// specially there, anything else is treated as "material".
const resourceCategories = [
  { value: 'material', label: 'Material' },
  { value: 'labor', label: 'Labor' },
  { value: 'machine', label: 'Machine' },
]

const AddResourceModal = ({
  opened,
  onClose,
  onSave,
  resource,
  hasCycle,
}: AddResourceModalProps) => {
  const [name, setName] = useState('')
  const [resourceType, setResourceType] = useState('material')
  const [unit, setUnit] = useState('board ft')
  const [availableQuantity, setAvailableQuantity] = useState(0)
  const [unitPrice, setUnitPrice] = useState(0)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (resource) {
      setName(resource.name)
      setResourceType(resource.resourceType)
      setUnit(resource.unit)
      setAvailableQuantity(resource.availableQuantity ?? 0)
      setUnitPrice(resource.unitPrice ?? 0)
    } else {
      setName('')
      setResourceType('material')
      setUnit('board ft')
      setAvailableQuantity(0)
      setUnitPrice(0)
    }

    setError(null)
  }, [resource, opened])

  const isValid =
    name.trim() !== '' &&
    resourceType.trim() !== '' &&
    unit.trim() !== '' &&
    (!hasCycle || (availableQuantity > 0 && unitPrice > 0))

  const handleSave = async () => {
    if (!isValid || isSubmitting) {
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      await onSave(
        {
          name,
          resource_type: resourceType,
          unit,
        },
        hasCycle
          ? {
              available_quantity: availableQuantity,
              unit_price: unitPrice,
            }
          : null,
      )
    } catch (submitError) {
      setError(
        getApiErrorMessage(
          submitError,
          'Unable to save resource. Please try again.',
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
      title={
        resource
          ? 'Edit Resource'
          : 'Add Resource'
      }
      centered
    >
      <Stack gap="md">
        <TextInput
          label="Name"
          placeholder="e.g. Wood"
          value={name}
          maxLength={100}
          onChange={(e) =>
            setName(e.currentTarget.value)
          }
        />

        <Select
          label="Category"
          data={resourceCategories}
          value={resourceType}
          onChange={(value) =>
            setResourceType(value ?? 'material')
          }
        />

        <Select
          label="Unit"
          data={units}
          value={unit}
          onChange={(value) =>
            setUnit(value ?? '')
          }
        />

        {!hasCycle && (
          <Alert color="yellow" icon={<AlertCircle size={18} />}>
            No active production cycle exists yet, so availability
            and unit price can&apos;t be saved for this resource
            right now.
          </Alert>
        )}

        <SimpleGrid cols={2}>
          <NumberInput
            label="Available Quantity"
            placeholder="e.g. 1250"
            value={availableQuantity}
            min={0}
            suffix={unit ? ` ${unit}` : undefined}
            disabled={!hasCycle}
            onChange={(value) =>
              setAvailableQuantity(Number(value))
            }
          />

          <NumberInput
            label="Unit Price"
            placeholder="e.g. 84"
            value={unitPrice}
            min={0}
            prefix="₱"
            thousandSeparator=","
            disabled={!hasCycle}
            onChange={(value) =>
              setUnitPrice(Number(value))
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

        <Group justify="flex-end">
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
            {resource
              ? 'Save Changes'
              : 'Add Resource'}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

export default AddResourceModal

import { useEffect, useState } from 'react'

import {
  Button,
  Group,
  Modal,
  NumberInput,
  Select,
  Stack,
  TextInput,
} from '@mantine/core'

import type { Resource } from '../types'

interface AddResourceModalProps {
  opened: boolean
  onClose: () => void
  onSave: (resource: Resource) => void
  resource?: Resource | null
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

const AddResourceModal = ({
  opened,
  onClose,
  onSave,
  resource,
}: AddResourceModalProps) => {
  const [resourceType, setResourceType] =
    useState('')

  const [availableQuantity, setAvailableQuantity] =
    useState(0)

  const [unitPrice, setUnitPrice] =
    useState(0)

  const [unit, setUnit] =
    useState('board ft')

  useEffect(() => {
    if (resource) {
      setResourceType(resource.resourceType)
      setAvailableQuantity(
        resource.availableQuantity,
      )
      setUnit(resource.unit)
      setUnitPrice(resource.unitPrice)
    } else {
      setResourceType('')
      setAvailableQuantity(0)
      setUnit('board ft')
      setUnitPrice(0)
    }
  }, [resource, opened])

  const isValid =
  resourceType.trim() !== '' &&
  availableQuantity > 0 &&
  unitPrice > 0

  const handleSave = () => {
    onSave({
      id: resource?.id ?? Date.now(),
      resourceType,
      availableQuantity,
      unit,
      unitPrice,
    })
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
          label="Resource Type"
          placeholder="e.g. Wood (board ft)"
          value={resourceType}
          onChange={(e) =>
            setResourceType(
              e.currentTarget.value,
            )
          }
        />

        <NumberInput
          label="Available Quantity"
          placeholder="Enter quantity"
          value={availableQuantity}
          onChange={(value) =>
            setAvailableQuantity(
              Number(value),
            )
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

        <NumberInput
          label="Unit Price"
          placeholder="0.00"
          value={unitPrice}
          onChange={(value) =>
            setUnitPrice(Number(value))
          }
          prefix="₱"
        />

        <Group justify="flex-end">
          <Button
            variant="default"
            onClick={onClose}
          >
            Cancel
          </Button>

          <Button onClick={handleSave} disabled={!isValid}>
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
import { useEffect, useState } from 'react'

import {
  Alert,
  Button,
  Group,
  Modal,
  NumberInput,
  SegmentedControl,
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
  ResourceResponse,
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
  // Soft-deleted (is_active = false) resources - candidates for the
  // "Reactivate Existing" mode below. Sourced from the database
  // (['resources-all'], see useResources.ts) - never hardcoded.
  // Already-active resources are never included, since re-adding one
  // would just hit the backend's own duplicate-name rejection - see
  // resourceApi.ts::fetchAllResourcesIncludingInactive.
  inactiveResources: ResourceResponse[]
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

// Also matches _classify_resource_type() (and its enforcement in
// backend/app/services/cycle_resource.py's
// _requires_positive_unit_price) - Labor is the only category exempt
// from needing a positive unit_price.
const isLaborResourceType = (resourceType: string) =>
  resourceType.trim().toLowerCase() === 'labor'

type NameMode = 'new' | 'reactivate'

const AddResourceModal = ({
  opened,
  onClose,
  onSave,
  resource,
  inactiveResources,
  hasCycle,
}: AddResourceModalProps) => {
  const [nameMode, setNameMode] = useState<NameMode>('new')
  const [selectedInactiveId, setSelectedInactiveId] = useState<
    string | null
  >(null)

  const [name, setName] = useState('')
  const [resourceType, setResourceType] = useState('material')
  const [unit, setUnit] = useState('board ft')
  const [availableQuantity, setAvailableQuantity] = useState(0)
  const [unitPrice, setUnitPrice] = useState(0)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Editing an existing resource is a rename/update of that specific
  // row - the reactivate-existing picker only applies when adding.
  const isAddMode = !resource

  useEffect(() => {
    if (resource) {
      setName(resource.name)
      setResourceType(resource.resourceType)
      setUnit(resource.unit)
      setAvailableQuantity(resource.availableQuantity ?? 0)
      setUnitPrice(
        isLaborResourceType(resource.resourceType)
          ? 0
          : resource.unitPrice ?? 0,
      )
    } else {
      setName('')
      setResourceType('material')
      setUnit('board ft')
      setAvailableQuantity(0)
      setUnitPrice(0)
    }

    setNameMode('new')
    setSelectedInactiveId(null)
    setError(null)
  }, [resource, opened])

  const handleSelectInactive = (value: string | null) => {
    setSelectedInactiveId(value)

    const selected = inactiveResources.find(
      (candidate) => String(candidate.id) === value,
    )

    if (selected) {
      setName(selected.name)
      setResourceType(selected.resource_type)
      setUnit(selected.unit)

      if (isLaborResourceType(selected.resource_type)) {
        setUnitPrice(0)
      }
    }
  }

  const handleNameModeChange = (value: string) => {
    const mode = value as NameMode
    setNameMode(mode)
    setSelectedInactiveId(null)

    if (mode === 'new') {
      setName('')
      setResourceType('material')
      setUnit('board ft')
    }
  }

  const isReactivating = isAddMode && nameMode === 'reactivate'

  // Labor's cost is tracked separately via Product.labor_cost (see
  // backend/app/services/cycle_resource.py's _requires_positive_unit_price,
  // which enforces the same exception server-side) - a Labor
  // CycleResource's unit_price is allowed to be 0.
  const isLabor = isLaborResourceType(resourceType)

  const isValid =
    name.trim() !== '' &&
    resourceType.trim() !== '' &&
    unit.trim() !== '' &&
    (!isReactivating || selectedInactiveId !== null) &&
    (!hasCycle ||
      (availableQuantity > 0 && (isLabor || unitPrice > 0)))

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

  const inactiveOptions = inactiveResources.map((candidate) => ({
    value: String(candidate.id),
    label: candidate.name,
  }))

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
        {isAddMode && inactiveResources.length > 0 && (
          <SegmentedControl
            fullWidth
            value={nameMode}
            onChange={handleNameModeChange}
            data={[
              { value: 'new', label: 'New Resource' },
              { value: 'reactivate', label: 'Reactivate Existing' },
            ]}
          />
        )}

        {isReactivating ? (
          <Select
            label="Name"
            placeholder="Select a previously deactivated resource"
            data={inactiveOptions}
            value={selectedInactiveId}
            onChange={handleSelectInactive}
            searchable
          />
        ) : (
          <TextInput
            label="Name"
            placeholder="e.g. Wood"
            value={name}
            maxLength={100}
            onChange={(e) =>
              setName(e.currentTarget.value)
            }
          />
        )}

        {isReactivating && selectedInactiveId && (
          <Alert color="blue" icon={<AlertCircle size={18} />}>
            This will reactivate the existing resource record (same
            ID, same product requirements) instead of creating a new
            one.
          </Alert>
        )}

        <Select
          label="Category"
          data={resourceCategories}
          value={resourceType}
          onChange={(value) => {
            const nextType = value ?? 'material'
            setResourceType(nextType)

            if (isLaborResourceType(nextType)) {
              setUnitPrice(0)
            }
          }}
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
            description={
              isLabor ? 'Not required for Labor' : undefined
            }
            placeholder="e.g. 84"
            value={unitPrice}
            min={0}
            prefix="₱"
            thousandSeparator=","
            disabled={!hasCycle || isLabor}
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
              : isReactivating
                ? 'Reactivate Resource'
                : 'Add Resource'}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

export default AddResourceModal

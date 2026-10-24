import { useEffect, useState } from 'react'

import {
  Alert,
  Autocomplete,
  Badge,
  Button,
  Card,
  Group,
  Loader,
  Modal,
  NumberInput,
  Select,
  SimpleGrid,
  Stack,
  Text,
} from '@mantine/core'

import {
  AlertCircle,
  Package,
} from 'lucide-react'

import { getApiErrorMessage } from '../../../api/apiError'

import type {
  Resource,
  ResourceSubmission,
} from '../types'

interface AddResourceModalProps {
  opened: boolean
  onClose: () => void
  onSave: (submission: ResourceSubmission) => Promise<void>
  resource?: Resource | null
  // Every resource in the catalog, active and inactive, carrying the
  // latest cycle's availability/price where one is configured - see
  // useResources.ts. The Name select lists all of them with a status
  // badge: this form only ever assigns an already-existing resource
  // to the current production cycle, it never creates a new Resource
  // record, so an arbitrary typed name is not a submittable value.
  selectableResources: Resource[]
  isExistingResourcesLoading: boolean
  isExistingResourcesError: boolean
  // Availability/price (CycleResource) can only be saved once a
  // production cycle exists - see useResources.ts. Adding an existing
  // resource is exactly that write, so with no cycle this form has
  // nothing it can save.
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

// Some existing resources (seeded before this list existed, or
// carrying a historical value like "hours" instead of "hrs") have a
// unit that isn't one of the choices above. Mantine's Select shows no
// selection at all for a value missing from `data` - which, left
// as-is, invites silently "fixing" it to whatever's closest just by
// opening Edit and hitting Save with Unit untouched-but-reset. Adding
// the resource's own current value as an extra option (only when it's
// not already one of the standard ones) keeps it visibly selected and
// unchanged unless the user deliberately picks something else -
// without renaming it, and without adding it to the list for every
// NEW resource going forward.
const unitOptions = (currentUnit: string) =>
  currentUnit && !units.some((option) => option.value === currentUnit)
    ? [...units, { value: currentUnit, label: currentUnit }]
    : units

// Matches backend/app/services/resource_utilization.py's
// _classify_resource_type() - "labor"/"machine" are recognized
// specially there, anything else is treated as "material".
const resourceCategories = [
  { value: 'material', label: 'Material' },
  { value: 'labor', label: 'Labor' },
  { value: 'machine', label: 'Machine' },
]

const categoryLabel = (resourceType: string) =>
  resourceCategories.find(
    (category) => category.value === resourceType.trim().toLowerCase(),
  )?.label ?? resourceType

// Also matches _classify_resource_type() (and its enforcement in
// backend/app/services/cycle_resource.py's
// _requires_positive_unit_price) - Labor is the only category exempt
// from needing a positive unit_price.
const isLaborResourceType = (resourceType: string) =>
  resourceType.trim().toLowerCase() === 'labor'

// Edit mode only: renaming this resource to a name that another
// catalog entry already uses would collide with the backend's
// normalized (lower(trim(name))) uniqueness rule - see
// backend/app/services/resource.py::_find_by_normalized_name, which
// applies the same comparison.
const normalizeResourceName = (value: string) =>
  value.trim().toLowerCase()

const DUPLICATE_ACTIVE_MESSAGE =
  'Another resource already uses this name. Choose a different name.'

const DUPLICATE_INACTIVE_MESSAGE =
  'An inactive resource already uses this name. Choose a different name.'

const AddResourceModal = ({
  opened,
  onClose,
  onSave,
  resource,
  selectableResources,
  isExistingResourcesLoading,
  isExistingResourcesError,
  hasCycle,
}: AddResourceModalProps) => {
  // Add mode: a selected catalog id (Select values are strings) -
  // never free text. Edit mode: the resource's own current name.
  const [selectedResourceId, setSelectedResourceId] = useState<
    string | null
  >(null)

  const [name, setName] = useState('')
  const [resourceType, setResourceType] = useState('material')
  const [unit, setUnit] = useState('board ft')
  const [availableQuantity, setAvailableQuantity] = useState(0)
  const [unitPrice, setUnitPrice] = useState(0)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Adding never creates a catalog entry, so the only add-mode write
  // is the selected resource's CycleResource availability/price.
  // Editing updates that one existing row.
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

    setSelectedResourceId(null)
    setError(null)
  }, [resource, opened])

  const selectedCatalogResource =
    selectableResources.find(
      (candidate) => String(candidate.id) === selectedResourceId,
    ) ?? null

  // The global category/unit come from the selected existing
  // resource in add mode (they describe the catalog row, which this
  // form does not modify) and from the editable fields in edit mode.
  const effectiveResourceType = isAddMode
    ? selectedCatalogResource?.resourceType ?? ''
    : resourceType

  // Labor's cost is tracked separately via Product.labor_cost (see
  // backend/app/services/cycle_resource.py's _requires_positive_unit_price,
  // which enforces the same exception server-side) - a Labor
  // CycleResource's unit_price is allowed to be 0.
  const isLabor = isLaborResourceType(effectiveResourceType)

  const effectiveUnit = isAddMode
    ? selectedCatalogResource?.unit ?? ''
    : unit

  // A name that another row already uses is never a valid rename,
  // whether that resource is active or inactive. The resource being
  // edited is excluded - mirroring the backend's exclude_id check in
  // update_resource.
  const duplicateResource =
    isAddMode || name.trim() === ''
      ? null
      : selectableResources.find(
          (candidate) =>
            candidate.id !== resource?.id &&
            normalizeResourceName(candidate.name) ===
              normalizeResourceName(name),
        ) ?? null

  const duplicateMessage = duplicateResource
    ? duplicateResource.isActive
      ? DUPLICATE_ACTIVE_MESSAGE
      : DUPLICATE_INACTIVE_MESSAGE
    : null

  // In add mode the modal writes only availability/price, so nothing
  // can be submitted without an active selection and a production
  // cycle. In edit mode the global fields can still be saved without
  // a cycle, matching the previous behavior.
  const canEditPricing = isAddMode
    ? Boolean(selectedCatalogResource?.isActive) && hasCycle
    : hasCycle

  const isAddValid =
    selectedCatalogResource !== null &&
    selectedCatalogResource.isActive &&
    hasCycle &&
    availableQuantity > 0 &&
    (isLabor || unitPrice > 0)

  const isEditValid =
    name.trim() !== '' &&
    duplicateResource === null &&
    resourceType.trim() !== '' &&
    unit.trim() !== '' &&
    (!hasCycle ||
      (availableQuantity >= 0 && (isLabor || unitPrice > 0)))

  const isValid = isAddMode ? isAddValid : isEditValid

  const hasCycleInventory =
    selectedCatalogResource !== null &&
    selectedCatalogResource.availableQuantity !== null

  // An inactive selection is never submittable, so it keeps the
  // plain "Add Resource" label rather than suggesting a save.
  const submitLabel = isAddMode
    ? selectedCatalogResource?.isActive && hasCycleInventory
      ? 'Save Changes'
      : 'Add Resource'
    : 'Save Changes'

  const handleSelectResource = (value: string | null) => {
    setSelectedResourceId(value)
    setError(null)

    const selected =
      selectableResources.find(
        (candidate) => String(candidate.id) === value,
      ) ?? null

    // Prefill the latest cycle's current values when this resource is
    // already configured, so an inventory update starts from what is
    // stored rather than from zero. A resource with no CycleResource
    // row starts empty and must be given a positive quantity.
    setAvailableQuantity(selected?.availableQuantity ?? 0)
    setUnitPrice(
      selected && isLaborResourceType(selected.resourceType)
        ? 0
        : selected?.unitPrice ?? 0,
    )
  }

  const handleSave = async () => {
    if (!isValid || isSubmitting) {
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      if (isAddMode) {
        if (!selectedCatalogResource) {
          return
        }

        // Only CycleResource is written here (create or update in
        // useResources.ts's savePricing) - never POST /api/resources.
        // Selecting an inactive resource never reaches this branch,
        // so nothing is silently reactivated or duplicated.
        await onSave({
          kind: 'inventory',
          resourceId: selectedCatalogResource.id,
          resourceName: selectedCatalogResource.name,
          pricing: {
            available_quantity: availableQuantity,
            unit_price: unitPrice,
          },
        })
      } else if (resource) {
        await onSave({
          kind: 'update',
          resourceId: resource.id,
          resourceName: name.trim(),
          data: {
            // Trimmed here as well as server-side, so the name shown
            // in the success notification is the one actually stored.
            name: name.trim(),
            resource_type: resourceType,
            unit: unit,
          },
          pricing: hasCycle
            ? {
                available_quantity: availableQuantity,
                unit_price: unitPrice,
              }
            : null,
        })
      }
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

  const nameOptions = [...selectableResources]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((candidate) => ({
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
        {isAddMode ? (
          <>
            <Select
              label="Name"
              placeholder={
                isExistingResourcesError
                  ? 'Resources unavailable'
                  : 'Select a resource'
              }
              description={
                isExistingResourcesLoading
                  ? 'Loading existing resources…'
                  : 'Choose an existing resource to make it available in the current production cycle.'
              }
              data={nameOptions}
              value={selectedResourceId}
              onChange={handleSelectResource}
              searchable
              // Typing only filters the options above - Mantine's
              // Select never turns the typed search into a value, so
              // an unlisted name can't be submitted.
              disabled={
                isExistingResourcesLoading ||
                isExistingResourcesError
              }
              nothingFoundMessage="No matching resource"
              rightSection={
                isExistingResourcesLoading ? (
                  <Loader size="xs" />
                ) : undefined
              }
              maxDropdownHeight={280}
              // Status is rendered as text (not color alone) next to
              // each existing resource, while the normal keyboard
              // navigation (arrow keys + Enter) still applies.
              renderOption={({ option }) => {
                const candidate = selectableResources.find(
                  (existing) =>
                    String(existing.id) === option.value,
                )

                return (
                  <Group
                    justify="space-between"
                    wrap="nowrap"
                    gap="sm"
                    w="100%"
                  >
                    <Text size="sm" truncate>
                      {option.label}
                    </Text>

                    {candidate && (
                      <Badge
                        size="sm"
                        variant="light"
                        color={
                          candidate.isActive ? 'green' : 'gray'
                        }
                      >
                        {candidate.isActive
                          ? 'Active'
                          : 'Inactive'}
                      </Badge>
                    )}
                  </Group>
                )
              }}
            />

            {isExistingResourcesError && (
              <Alert
                color="yellow"
                icon={<AlertCircle size={18} />}
              >
                Existing resources could not be loaded, so nothing
                can be selected right now. Close this dialog and
                try again.
              </Alert>
            )}

            {!isExistingResourcesLoading &&
              !isExistingResourcesError &&
              selectableResources.length === 0 && (
                <Alert
                  color="blue"
                  icon={<AlertCircle size={18} />}
                >
                  No resources exist in the catalog yet. A resource
                  has to be created before it can be added to a
                  production cycle.
                </Alert>
              )}

            {selectedCatalogResource && (
              <Card withBorder radius="md" padding="sm">
                <Group
                  justify="space-between"
                  wrap="nowrap"
                  gap="sm"
                >
                  <Group gap="sm" wrap="nowrap">
                    <Package size={18} />

                    <Stack gap={2}>
                      <Text fw={600} size="sm">
                        {selectedCatalogResource.name}
                      </Text>

                      <Text size="xs" c="dimmed">
                        {categoryLabel(
                          selectedCatalogResource.resourceType,
                        )}{' '}
                        • {selectedCatalogResource.unit}
                      </Text>
                    </Stack>
                  </Group>

                  <Badge
                    variant="light"
                    color={
                      selectedCatalogResource.isActive
                        ? 'green'
                        : 'gray'
                    }
                  >
                    {selectedCatalogResource.isActive
                      ? 'Active'
                      : 'Inactive'}
                  </Badge>
                </Group>
              </Card>
            )}

            {selectedCatalogResource &&
              !selectedCatalogResource.isActive && (
                <Alert
                  color="orange"
                  icon={<AlertCircle size={18} />}
                >
                  This resource is inactive, so it can&apos;t be
                  added to a production cycle. Choose an active
                  resource - nothing is reactivated or changed by
                  this form.
                </Alert>
              )}
          </>
        ) : (
          <>
            <Autocomplete
              label="Name"
              placeholder="e.g. Wood"
              description="Type a different name to rename this resource."
              data={selectableResources.map(
                (candidate) => candidate.name,
              )}
              value={name}
              onChange={setName}
              maxLength={100}
              error={duplicateMessage}
              // Status is rendered as text (not color alone) next to
              // each existing resource, while Autocomplete's normal
              // keyboard navigation (arrow keys + Enter) still applies.
              renderOption={({ option }) => {
                const candidate = selectableResources.find(
                  (existing) => existing.name === option.value,
                )

                return (
                  <Group
                    justify="space-between"
                    wrap="nowrap"
                    gap="sm"
                    w="100%"
                  >
                    <Text size="sm" truncate>
                      {option.value}
                    </Text>

                    {candidate && (
                      <Badge
                        size="sm"
                        variant="light"
                        color={
                          candidate.isActive ? 'green' : 'gray'
                        }
                      >
                        {candidate.isActive
                          ? 'Active'
                          : 'Inactive'}
                      </Badge>
                    )}
                  </Group>
                )
              }}
            />

            {isExistingResourcesError && (
              <Alert
                color="yellow"
                icon={<AlertCircle size={18} />}
              >
                Existing resources could not be loaded, so a
                duplicate name can&apos;t be checked here. The
                server will still reject an existing name when you
                save.
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
              data={unitOptions(unit)}
              value={unit}
              onChange={(value) =>
                setUnit(value ?? '')
              }
            />
          </>
        )}

        {!hasCycle && (
          <Alert
            color="yellow"
            icon={<AlertCircle size={18} />}
          >
            {isAddMode
              ? 'No production cycle exists yet, so a resource can’t be added right now.'
              : 'No production cycle exists yet, so availability and unit price can’t be saved for this resource right now.'}
          </Alert>
        )}

        <SimpleGrid cols={2}>
          <NumberInput
            label="Available Quantity"
            placeholder="e.g. 1250"
            value={availableQuantity}
            min={0}
            suffix={
              effectiveUnit ? ` ${effectiveUnit}` : undefined
            }
            disabled={!canEditPricing}
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
            disabled={!canEditPricing || isLabor}
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
            {submitLabel}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

export default AddResourceModal

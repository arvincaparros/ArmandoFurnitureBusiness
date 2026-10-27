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
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
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
  // useResources.ts. The "Use Existing" Name select lists all of them
  // with a status badge and assigns the selected one to the current
  // production cycle; it never creates a Resource record, so an
  // arbitrary typed name is not a submittable value there. Creating
  // a catalog entry is the separate "Create New" mode, which also
  // uses this list to block a name another resource already has.
  selectableResources: Resource[]
  isExistingResourcesLoading: boolean
  isExistingResourcesError: boolean
  // Availability/price (CycleResource) can only be saved once a
  // production cycle exists - see useResources.ts. Assigning an
  // existing resource is exactly that write, so with no cycle that
  // mode has nothing it can save. Creating a catalog entry does not
  // depend on a cycle: the resource is created either way, and only
  // its availability/price has to wait for one.
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

// Add mode covers two different writes; edit mode is neither. "Use
// Existing" assigns an already-catalogued resource to the current
// production cycle (CycleResource only), while "Create New" is the
// one path that inserts a new global Resource record.
type AddMode = 'existing' | 'create'

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

  const [addMode, setAddMode] = useState<AddMode>('existing')

  const [name, setName] = useState('')
  const [resourceType, setResourceType] = useState('material')
  const [unit, setUnit] = useState('board ft')
  const [availableQuantity, setAvailableQuantity] = useState(0)
  const [unitPrice, setUnitPrice] = useState(0)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Adding either assigns an existing catalog entry (the only
  // add-mode write then being its CycleResource availability/price)
  // or creates a new catalog entry. Editing updates one existing row.
  const isAddMode = !resource

  const isCreatingNew = isAddMode && addMode === 'create'

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
    setAddMode('existing')
    setError(null)
  }, [resource, opened])

  const selectedCatalogResource =
    selectableResources.find(
      (candidate) => String(candidate.id) === selectedResourceId,
    ) ?? null

  // The global category/unit come from the selected existing
  // resource in "Use Existing" mode (they describe the catalog row,
  // which that form does not modify) and from the editable fields
  // otherwise - "Create New" and edit both own their own values.
  const effectiveResourceType =
    isAddMode && !isCreatingNew
      ? selectedCatalogResource?.resourceType ?? ''
      : resourceType

  // Labor's cost is tracked separately via Product.labor_cost (see
  // backend/app/services/cycle_resource.py's _requires_positive_unit_price,
  // which enforces the same exception server-side) - a Labor
  // CycleResource's unit_price is allowed to be 0.
  const isLabor = isLaborResourceType(effectiveResourceType)

  const effectiveUnit =
    isAddMode && !isCreatingNew
      ? selectedCatalogResource?.unit ?? ''
      : unit

  // A name that another row already uses is never a valid rename or a
  // valid new resource, whether that resource is active or inactive.
  // In edit mode the resource being edited is excluded - mirroring the
  // backend's exclude_id check in update_resource. "Use Existing"
  // assigns an already-catalogued row, so it checks nothing here.
  const duplicateResource =
    (isAddMode && !isCreatingNew) || name.trim() === ''
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

  // Availability/price (CycleResource) need a production cycle
  // whatever the mode. "Use Existing" also needs an active selection,
  // since that write is the only thing it can submit.
  const canEditPricing =
    isAddMode && !isCreatingNew
      ? Boolean(selectedCatalogResource?.isActive) && hasCycle
      : hasCycle

  const isAddValid =
    selectedCatalogResource !== null &&
    selectedCatalogResource.isActive &&
    hasCycle &&
    availableQuantity > 0 &&
    (isLabor || unitPrice > 0)

  // Creating the catalog row does not depend on a cycle - only its
  // availability/price does, so those are required (and editable) only
  // when a cycle exists.
  const isCreateValid =
    name.trim() !== '' &&
    duplicateResource === null &&
    resourceType.trim() !== '' &&
    unit.trim() !== '' &&
    (!hasCycle ||
      (availableQuantity > 0 && (isLabor || unitPrice > 0)))

  const isEditValid =
    name.trim() !== '' &&
    duplicateResource === null &&
    resourceType.trim() !== '' &&
    unit.trim() !== '' &&
    (!hasCycle ||
      (availableQuantity >= 0 && (isLabor || unitPrice > 0)))

  const isValid = isAddMode
    ? isCreatingNew
      ? isCreateValid
      : isAddValid
    : isEditValid

  const hasCycleInventory =
    selectedCatalogResource !== null &&
    selectedCatalogResource.availableQuantity !== null

  // An inactive selection is never submittable, so it keeps the
  // plain "Add Resource" label rather than suggesting a save.
  const submitLabel = isAddMode
    ? isCreatingNew
      ? 'Create Resource'
      : selectedCatalogResource?.isActive && hasCycleInventory
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

  // Switching between the two add modes starts from a clean form: a
  // typing-in-progress in one mode, or a quantity prefilled from a
  // resource selected in the other, must never leak into the other
  // mode's submission.
  const handleModeChange = (value: string) => {
    const nextMode: AddMode =
      value === 'create' ? 'create' : 'existing'

    setAddMode(nextMode)
    setSelectedResourceId(null)
    setName('')
    setResourceType('material')
    setUnit('board ft')
    setAvailableQuantity(0)
    setUnitPrice(0)
    setError(null)
  }

  const handleSave = async () => {
    if (!isValid || isSubmitting) {
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      if (isCreatingNew) {
        // The one branch that inserts a new global Resource record
        // (ResourcesPage.tsx's createResource -> POST /api/resources).
        // Pricing is written afterwards against the id the server
        // assigned, so the cycle reuses that id rather than creating
        // a second catalog row.
        await onSave({
          kind: 'create',
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
      } else if (isAddMode) {
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

  // Category and Unit describe the catalog row itself, so the same two
  // controls serve "Create New" and edit - the fields the resource
  // form already had. "Use Existing" never edits them: they are read
  // from the selected catalog row and shown read-only on its card.
  const categoryField = (
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
  )

  const unitField = (
    <Select
      label="Unit"
      data={unitOptions(unit)}
      value={unit}
      onChange={(value) => setUnit(value ?? '')}
    />
  )

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
        {isAddMode && (
          // Two distinct writes behind one action: assigning an
          // already-catalogued resource to the current cycle, or
          // creating a new catalog resource. Defaults to "Use
          // Existing", so the existing selection workflow is
          // unchanged for anyone who doesn't switch.
          <SegmentedControl
            value={addMode}
            onChange={handleModeChange}
            data={[
              { value: 'existing', label: 'Use Existing' },
              { value: 'create', label: 'Create New' },
            ]}
            fullWidth
          />
        )}

        {isCreatingNew ? (
          <>
            <TextInput
              label="Name"
              placeholder="e.g. Sandpaper"
              description="Give the new resource a unique name."
              value={name}
              onChange={(event) => {
                setName(event.currentTarget.value)
                setError(null)
              }}
              maxLength={100}
              error={duplicateMessage}
            />

            {categoryField}
            {unitField}
          </>
        ) : isAddMode ? (
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
                  No resources exist in the catalog yet. Switch to
                  Create New above to add the first one.
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

            {categoryField}
            {unitField}
          </>
        )}

        {!hasCycle && (
          <Alert
            color="yellow"
            icon={<AlertCircle size={18} />}
          >
            {isCreatingNew
              ? 'No production cycle exists yet, so availability and unit price can’t be saved now. The resource will still be created in the catalog and can be added to a cycle once one exists.'
              : isAddMode
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

import { useState } from 'react'

import {
  ActionIcon,
  Alert,
  Button,
  Divider,
  Group,
  Loader,
  NumberInput,
  Select,
  Stack,
  Text,
} from '@mantine/core'

import { AlertCircle, Check, Plus, X } from 'lucide-react'

import { getApiErrorMessage } from '../../../api/apiError'

import useProductResourceRequirements from '../hooks/useProductResourceRequirements'

import RequirementRow from './RequirementRow'

interface ProductResourceRequirementsSectionProps {
  productId: number
}

const ProductResourceRequirementsSection = ({
  productId,
}: ProductResourceRequirementsSectionProps) => {
  const {
    requirements,
    availableResourcesForNew,
    isLoading,
    isError,
    createRequirement,
    updateRequirement,
    deleteRequirement,
  } = useProductResourceRequirements(productId)

  const [isAdding, setIsAdding] = useState(false)
  const [newResourceId, setNewResourceId] = useState<
    string | null
  >(null)
  const [newQuantity, setNewQuantity] = useState<number | ''>('')
  const [isSubmittingNew, setIsSubmittingNew] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)

  const resetAddForm = () => {
    setIsAdding(false)
    setNewResourceId(null)
    setNewQuantity('')
    setAddError(null)
  }

  const isNewValid =
    newResourceId !== null &&
    newQuantity !== '' &&
    newQuantity > 0

  const handleConfirmAdd = async () => {
    if (!isNewValid) {
      return
    }

    setIsSubmittingNew(true)
    setAddError(null)

    try {
      await createRequirement({
        resource_id: Number(newResourceId),
        quantity_required: newQuantity as number,
      })

      resetAddForm()
    } catch (error) {
      setAddError(
        getApiErrorMessage(
          error,
          'Unable to add requirement. Please try again.',
        ),
      )
    } finally {
      setIsSubmittingNew(false)
    }
  }

  const resourceOptions = availableResourcesForNew.map(
    (resource) => ({
      value: String(resource.id),
      label: `${resource.name} (${resource.unit})`,
    }),
  )

  return (
    <Stack gap="xs">
      <Divider
        my="xs"
        label="Resource Requirements"
        labelPosition="center"
      />

      {isLoading ? (
        <Group justify="center" py="sm">
          <Loader size="sm" />
        </Group>
      ) : isError ? (
        <Alert color="red" icon={<AlertCircle size={18} />}>
          Unable to load resource requirements.
        </Alert>
      ) : (
        <>
          {requirements.length === 0 && !isAdding && (
            <Text size="sm" c="dimmed" ta="center" py="xs">
              No resource requirements yet.
            </Text>
          )}

          {requirements.map((requirement) => (
            <RequirementRow
              key={requirement.id}
              requirement={requirement}
              onUpdate={updateRequirement}
              onDelete={deleteRequirement}
            />
          ))}

          {isAdding ? (
            <Stack gap="xs">
              <Group wrap="nowrap" gap="sm">
                <Select
                  size="sm"
                  style={{ flex: 1 }}
                  placeholder="Select resource"
                  data={resourceOptions}
                  value={newResourceId}
                  onChange={setNewResourceId}
                  searchable
                  disabled={isSubmittingNew}
                />

                <NumberInput
                  size="sm"
                  w={140}
                  placeholder="Quantity"
                  value={newQuantity}
                  min={0}
                  decimalScale={4}
                  disabled={isSubmittingNew}
                  onChange={(value) =>
                    setNewQuantity(
                      value === '' ? '' : Number(value),
                    )
                  }
                />

                <ActionIcon
                  color="green"
                  disabled={!isNewValid}
                  loading={isSubmittingNew}
                  onClick={() => {
                    void handleConfirmAdd()
                  }}
                >
                  <Check size={16} />
                </ActionIcon>

                <ActionIcon
                  variant="default"
                  disabled={isSubmittingNew}
                  onClick={resetAddForm}
                >
                  <X size={16} />
                </ActionIcon>
              </Group>

              {addError && (
                <Text size="xs" c="red">
                  {addError}
                </Text>
              )}
            </Stack>
          ) : (
            <Button
              variant="light"
              size="xs"
              leftSection={<Plus size={14} />}
              onClick={() => setIsAdding(true)}
              disabled={availableResourcesForNew.length === 0}
            >
              Add Requirement
            </Button>
          )}

          {!isAdding &&
            availableResourcesForNew.length === 0 && (
              <Text size="xs" c="dimmed">
                All active resources are already assigned to
                this product.
              </Text>
            )}
        </>
      )}
    </Stack>
  )
}

export default ProductResourceRequirementsSection

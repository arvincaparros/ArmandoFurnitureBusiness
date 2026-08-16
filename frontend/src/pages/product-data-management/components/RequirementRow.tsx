import { useState } from 'react'

import {
  ActionIcon,
  Badge,
  Group,
  NumberInput,
  Popover,
  Stack,
  Text,
} from '@mantine/core'

import { Trash2 } from 'lucide-react'

import { getApiErrorMessage } from '../../../api/apiError'

import type { ResolvedRequirement } from '../api/productResourceAdapter'
import type { ProductResourceRequirementUpdateRequest } from '../api/productResourceTypes'

interface RequirementRowProps {
  requirement: ResolvedRequirement
  onUpdate: (args: {
    resourceId: number
    data: ProductResourceRequirementUpdateRequest
  }) => Promise<unknown>
  onDelete: (resourceId: number) => Promise<unknown>
}

const RequirementRow = ({
  requirement,
  onUpdate,
  onDelete,
}: RequirementRowProps) => {
  const [quantity, setQuantity] = useState<number | ''>(
    requirement.quantityRequired,
  )

  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const [isDeleting, setIsDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(
    null,
  )

  const [confirmOpened, setConfirmOpened] = useState(false)

  const handleQuantityBlur = async () => {
    if (
      quantity === '' ||
      quantity <= 0 ||
      quantity === requirement.quantityRequired
    ) {
      setQuantity(requirement.quantityRequired)
      return
    }

    setIsSaving(true)
    setSaveError(null)

    try {
      await onUpdate({
        resourceId: requirement.resourceId,
        data: { quantity_required: quantity },
      })
    } catch (error) {
      setQuantity(requirement.quantityRequired)
      setSaveError(
        getApiErrorMessage(
          error,
          'Unable to update quantity. Please try again.',
        ),
      )
    } finally {
      setIsSaving(false)
    }
  }

  const handleConfirmDelete = async () => {
    setIsDeleting(true)
    setDeleteError(null)

    try {
      await onDelete(requirement.resourceId)
    } catch (error) {
      setDeleteError(
        getApiErrorMessage(
          error,
          'Unable to remove requirement. Please try again.',
        ),
      )
      setIsDeleting(false)
      setConfirmOpened(false)
    }
  }

  return (
    <Stack gap={2}>
      <Group wrap="nowrap" gap="sm">
        <Group gap={6} wrap="nowrap" style={{ flex: 1 }}>
          <Text size="sm">
            {requirement.resourceName}
          </Text>

          {requirement.resourceUnit && (
            <Text size="xs" c="dimmed">
              ({requirement.resourceUnit})
            </Text>
          )}

          {!requirement.resourceIsActive && (
            <Badge color="gray" size="sm" variant="light">
              Inactive
            </Badge>
          )}
        </Group>

        <NumberInput
          size="sm"
          w={140}
          value={quantity}
          min={0}
          decimalScale={4}
          disabled={isSaving || isDeleting}
          onChange={(value) =>
            setQuantity(value === '' ? '' : Number(value))
          }
          onBlur={handleQuantityBlur}
        />

        <Popover
          opened={confirmOpened}
          onChange={setConfirmOpened}
          position="top-end"
          withArrow
        >
          <Popover.Target>
            <ActionIcon
              variant="subtle"
              color="red"
              disabled={isDeleting}
              onClick={() => setConfirmOpened((o) => !o)}
            >
              <Trash2 size={16} />
            </ActionIcon>
          </Popover.Target>

          <Popover.Dropdown>
            <Stack gap="xs">
              <Text size="sm">
                Remove {requirement.resourceName}?
              </Text>

              <Group gap="xs" justify="flex-end">
                <ActionIcon
                  variant="default"
                  size="sm"
                  onClick={() => setConfirmOpened(false)}
                >
                  ✕
                </ActionIcon>

                <ActionIcon
                  color="red"
                  size="sm"
                  loading={isDeleting}
                  onClick={handleConfirmDelete}
                >
                  <Trash2 size={14} />
                </ActionIcon>
              </Group>
            </Stack>
          </Popover.Dropdown>
        </Popover>
      </Group>

      {saveError && (
        <Text size="xs" c="red">
          {saveError}
        </Text>
      )}

      {deleteError && (
        <Text size="xs" c="red">
          {deleteError}
        </Text>
      )}
    </Stack>
  )
}

export default RequirementRow

import { useState } from 'react'

import {
  Button,
  Group,
  NumberInput,
  SimpleGrid,
  Stack,
  Textarea,
  TextInput,
} from '@mantine/core'

import type {
  OpeningInventoryItemInput,
  OpeningInventorySetResponse,
} from '../api/openingInventoryTypes'

interface ProductSummary {
  id: number
  name: string
}

interface OpeningInventoryFormProps {
  products: ProductSummary[]
  draftSet: OpeningInventorySetResponse | null
  isSaving: boolean
  onSave: (
    effectiveDate: string,
    notes: string | null,
    items: OpeningInventoryItemInput[],
  ) => Promise<unknown>
}

const toDateInputValue = (value: string | null) =>
  value ? value.slice(0, 10) : new Date().toISOString().slice(0, 10)

// State holds only the user's EDITS, overlaid on the draft that
// arrives from the server. Nothing is copied into state on load, so
// there is no effect to sync and no stale-copy window while the draft
// and the product list are still being fetched - each field simply
// falls back to the server value, then to zero.
const OpeningInventoryForm = ({
  products,
  draftSet,
  isSaving,
  onSave,
}: OpeningInventoryFormProps) => {
  const [dateEdit, setDateEdit] = useState<string | null>(null)
  const [notesEdit, setNotesEdit] = useState<string | null>(null)
  const [quantityEdits, setQuantityEdits] = useState<
    Record<number, number | string>
  >({})

  const effectiveDate =
    dateEdit ?? toDateInputValue(draftSet?.effective_date ?? null)

  const notes = notesEdit ?? draftSet?.notes ?? ''

  // One NumberInput per ACTIVE product, prefilled from the draft and
  // 0 when absent. Deliberate rather than leaving untouched products
  // blank: review is refused unless every applicable product carries
  // an EXPLICIT quantity, and a missing row is an incomplete
  // declaration rather than an implied zero - so submitting the whole
  // form produces a complete set by construction.
  const declaredQuantity = (productId: number) => {
    if (productId in quantityEdits) {
      return quantityEdits[productId]
    }

    const item = draftSet?.items.find(
      (candidate) => candidate.product_id === productId,
    )

    return item ? Number(item.quantity) : 0
  }

  const handleSave = () =>
    onSave(
      `${effectiveDate}T00:00:00`,
      notes.trim() === '' ? null : notes,
      products.map((product) => ({
        product_id: product.id,
        quantity: Number(declaredQuantity(product.id) ?? 0),
      })),
    )

  return (
    <Stack gap="md">
      <Group grow align="flex-start">
        <TextInput
          label="Effective date"
          description="The date these balances were counted as of."
          type="date"
          value={effectiveDate}
          onChange={(event) =>
            setDateEdit(event.currentTarget.value)
          }
        />
      </Group>

      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="sm">
        {products.map((product) => (
          <NumberInput
            key={product.id}
            label={product.name}
            min={0}
            value={declaredQuantity(product.id)}
            onChange={(value) =>
              setQuantityEdits((current) => ({
                ...current,
                [product.id]: value,
              }))
            }
          />
        ))}
      </SimpleGrid>

      <Textarea
        label="Notes"
        autosize
        minRows={2}
        value={notes}
        onChange={(event) => setNotesEdit(event.currentTarget.value)}
      />

      <Group justify="flex-end">
        <Button onClick={handleSave} loading={isSaving}>
          Save draft
        </Button>
      </Group>
    </Stack>
  )
}

export default OpeningInventoryForm

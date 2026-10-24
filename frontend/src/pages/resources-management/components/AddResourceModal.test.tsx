import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import { describe, expect, it, vi } from 'vitest'

import AddResourceModal from './AddResourceModal'

import type { Resource } from '../types'

// As built by useResources.ts from GET /api/resources?include_inactive=true
// plus the latest cycle's CycleResource rows - availability/price are
// null when the resource has no row in that cycle yet.
const selectableResources: Resource[] = [
  {
    id: 1,
    name: 'Wood',
    resourceType: 'material',
    unit: 'board ft',
    isActive: true,
    availableQuantity: 1000,
    unitPrice: 50,
  },
  {
    id: 2,
    name: 'Wood Glue',
    resourceType: 'material',
    unit: 'liter',
    isActive: true,
    availableQuantity: null,
    unitPrice: null,
  },
  {
    id: 3,
    name: 'Epoxy',
    resourceType: 'material',
    unit: 'liter',
    isActive: false,
    availableQuantity: null,
    unitPrice: null,
  },
  {
    id: 4,
    name: 'Nails',
    resourceType: 'material',
    unit: 'pcs',
    isActive: false,
    availableQuantity: null,
    unitPrice: null,
  },
]

const woodResource = selectableResources[0]

interface RenderModalOptions {
  resource?: Resource | null
  isLoading?: boolean
  isError?: boolean
  hasCycle?: boolean
  selectable?: Resource[]
}

const renderModal = ({
  resource = null,
  isLoading = false,
  isError = false,
  hasCycle = true,
  selectable = selectableResources,
}: RenderModalOptions = {}) => {
  const onSave = vi.fn().mockResolvedValue(undefined)

  render(
    <MantineProvider>
      <AddResourceModal
        opened
        onClose={vi.fn()}
        onSave={onSave}
        resource={resource}
        selectableResources={selectable}
        isExistingResourcesLoading={isLoading}
        isExistingResourcesError={isError}
        hasCycle={hasCycle}
      />
    </MantineProvider>,
  )

  return { onSave }
}

const openNameDropdown = async () => {
  // Mantine's Select listbox reuses the input's label through
  // aria-labelledby, so getByLabelText('Name') matches both - the
  // combobox role targets the input itself.
  const input = await screen.findByRole('combobox', { name: 'Name' })
  await userEvent.click(input)

  return input
}

const findOptionByText = (text: string): HTMLElement => {
  const option = screen
    .getAllByText(text)
    .map((element) => element.closest('[role="option"]'))
    .find((candidate) => candidate !== null)

  if (!(option instanceof HTMLElement)) {
    throw new Error(`No dropdown option found for "${text}"`)
  }

  return option
}

const selectResource = async (name: string) => {
  await openNameDropdown()
  await userEvent.click(findOptionByText(name))
}

const fillCyclePricing = async (
  quantity: string,
  price: string,
) => {
  const quantityInput = screen.getByLabelText('Available Quantity')
  await userEvent.clear(quantityInput)
  await userEvent.type(quantityInput, quantity)

  const priceInput = screen.getByLabelText('Unit Price')
  await userEvent.clear(priceInput)
  await userEvent.type(priceInput, price)
}

describe('AddResourceModal', () => {
  it('no longer renders the Reactivate Existing tab', async () => {
    renderModal()

    await screen.findByRole('combobox', { name: 'Name' })

    expect(
      screen.queryByText('Reactivate Existing'),
    ).not.toBeInTheDocument()
    expect(screen.queryByText('New Resource')).not.toBeInTheDocument()
    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument()
    expect(screen.queryByRole('radio')).not.toBeInTheDocument()
  })

  it('lists existing resources with their Active and Inactive badges', async () => {
    renderModal()
    await openNameDropdown()

    expect(await screen.findByText('Wood')).toBeInTheDocument()
    expect(screen.getByText('Wood Glue')).toBeInTheDocument()
    expect(screen.getByText('Epoxy')).toBeInTheDocument()
    expect(screen.getByText('Nails')).toBeInTheDocument()

    expect(
      within(findOptionByText('Wood')).getByText('Active'),
    ).toBeInTheDocument()
    expect(
      within(findOptionByText('Wood Glue')).getByText('Active'),
    ).toBeInTheDocument()
    expect(
      within(findOptionByText('Epoxy')).getByText('Inactive'),
    ).toBeInTheDocument()
    expect(
      within(findOptionByText('Nails')).getByText('Inactive'),
    ).toBeInTheDocument()

    // Status text is present per option, not color alone.
    expect(screen.getAllByText('Active')).toHaveLength(2)
    expect(screen.getAllByText('Inactive')).toHaveLength(2)
  })

  it('filters existing options as the user types, without offering a create action', async () => {
    renderModal()
    const input = await openNameDropdown()

    await userEvent.type(input, 'glue')

    expect(screen.getByText('Wood Glue')).toBeInTheDocument()
    expect(screen.queryByText('Wood')).not.toBeInTheDocument()
    expect(screen.queryByText('Epoxy')).not.toBeInTheDocument()
    expect(screen.queryByText('Nails')).not.toBeInTheDocument()

    // A selection-only component has no "create <typed name>" row.
    expect(screen.queryByText(/create/i)).not.toBeInTheDocument()
  })

  it('cannot submit an arbitrary typed name', async () => {
    const { onSave } = renderModal()
    const input = await openNameDropdown()

    await userEvent.type(input, 'Sandpaper 120 Grit')

    expect(
      screen.getByText('No matching resource'),
    ).toBeInTheDocument()

    // No resource is selected, so the pricing fields and submit stay
    // disabled - the typed search text is never a value.
    expect(
      screen.getByLabelText('Available Quantity'),
    ).toBeDisabled()

    const submit = screen.getByRole('button', {
      name: 'Add Resource',
    })

    expect(submit).toBeDisabled()

    await userEvent.click(submit)

    expect(onSave).not.toHaveBeenCalled()
  })

  it('selects an existing active resource without a duplicate-name error', async () => {
    const { onSave } = renderModal()

    await selectResource('Wood')

    expect(
      screen.queryByText(/already exists/i),
    ).not.toBeInTheDocument()

    // Selected resource is shown with its status and catalog details.
    expect(
      await screen.findByRole('combobox', { name: 'Name' }),
    ).toHaveValue('Wood')
    expect(
      screen.getByText(/Material\s*•\s*board ft/),
    ).toBeInTheDocument()
    expect(
      screen.getAllByText('Active').length,
    ).toBeGreaterThan(0)

    // Existing cycle values are prefilled, so this is an inventory
    // update rather than a blind overwrite.
    await userEvent.click(
      screen.getByRole('button', { name: 'Save Changes' }),
    )

    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith({
        kind: 'inventory',
        resourceId: 1,
        resourceName: 'Wood',
        pricing: {
          available_quantity: 1000,
          unit_price: 50,
        },
      }),
    )
  })

  it('submits availability and price for an active resource with no cycle row yet', async () => {
    const { onSave } = renderModal()

    await selectResource('Wood Glue')

    expect(
      screen.queryByText(/already exists/i),
    ).not.toBeInTheDocument()

    const submit = screen.getByRole('button', {
      name: 'Add Resource',
    })

    // No CycleResource row yet: a positive quantity/price is required.
    expect(submit).toBeDisabled()

    await fillCyclePricing('250', '12')

    expect(submit).toBeEnabled()

    await userEvent.click(submit)

    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith({
        kind: 'inventory',
        resourceId: 2,
        resourceName: 'Wood Glue',
        pricing: {
          available_quantity: 250,
          unit_price: 12,
        },
      }),
    )
  })

  it('blocks an inactive resource instead of reactivating it', async () => {
    const { onSave } = renderModal()

    await selectResource('Epoxy')

    expect(
      screen.getByText(/inactive, so it can't be added/i),
    ).toBeInTheDocument()

    expect(
      screen.getByLabelText('Available Quantity'),
    ).toBeDisabled()
    expect(screen.getByLabelText('Unit Price')).toBeDisabled()

    const submit = screen.getByRole('button', {
      name: 'Add Resource',
    })

    expect(submit).toBeDisabled()

    await userEvent.click(submit)

    expect(onSave).not.toHaveBeenCalled()
  })

  it('requires an active selection and a production cycle to submit', async () => {
    renderModal({ hasCycle: false })

    await selectResource('Wood Glue')

    expect(
      screen.getByText(/No production cycle exists yet/i),
    ).toBeInTheDocument()
    expect(
      screen.getByLabelText('Available Quantity'),
    ).toBeDisabled()
    expect(
      screen.getByRole('button', { name: 'Add Resource' }),
    ).toBeDisabled()
  })

  it('shows a loading state while existing resources are fetched', async () => {
    renderModal({ isLoading: true })

    expect(
      await screen.findByText('Loading existing resources…'),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('combobox', { name: 'Name' }),
    ).toBeDisabled()
    expect(
      screen.getByRole('button', { name: 'Add Resource' }),
    ).toBeDisabled()
  })

  it('warns when the existing list fails to load and blocks submission', async () => {
    renderModal({ isError: true })

    expect(
      await screen.findByText(/Existing resources could not be loaded/i),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('combobox', { name: 'Name' }),
    ).toBeDisabled()
    expect(
      screen.getByRole('button', { name: 'Add Resource' }),
    ).toBeDisabled()
  })

  it('explains an empty catalog and blocks submission', async () => {
    renderModal({ selectable: [] })

    expect(
      await screen.findByText(/No resources exist in the catalog yet/i),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: 'Add Resource' }),
    ).toBeDisabled()
  })

  it('does not flag the resource being edited as a duplicate of itself', async () => {
    const { onSave } = renderModal({
      resource: woodResource,
    })

    expect(
      await screen.findByRole('combobox', { name: 'Name' }),
    ).toHaveValue('Wood')
    expect(
      screen.queryByText(/already uses this name/i),
    ).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Save Changes' }),
    ).toBeEnabled()

    await userEvent.click(
      screen.getByRole('button', { name: 'Save Changes' }),
    )

    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith({
        kind: 'update',
        resourceId: 1,
        resourceName: 'Wood',
        data: {
          name: 'Wood',
          resource_type: 'material',
          unit: 'board ft',
        },
        pricing: {
          available_quantity: 1000,
          unit_price: 50,
        },
      }),
    )
  })

  it('blocks renaming a resource to another existing name', async () => {
    const { onSave } = renderModal({
      resource: woodResource,
    })
    const input = await screen.findByRole('combobox', {
      name: 'Name',
    })

    await userEvent.clear(input)
    await userEvent.type(input, 'Nails')

    expect(
      screen.getByText(/inactive resource already uses this name/i),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Save Changes' }),
    ).toBeDisabled()

    await userEvent.click(
      screen.getByRole('button', { name: 'Save Changes' }),
    )

    expect(onSave).not.toHaveBeenCalled()
  })
})

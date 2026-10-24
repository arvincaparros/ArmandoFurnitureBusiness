import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import { Notifications, notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ResourcesPage from './ResourcesPage'
import {
  createCycleResource,
  updateCycleResource,
} from './api/cycleResourceApi'
import { ThemeProvider } from '../../theme/ThemeContext'

vi.mock('../../hooks/useLatestProductionCycle', () => ({
  default: () => ({ cycleId: 1, hasCycle: true, isLoading: false, isError: false }),
}))

const { catalog, updateResourceMock } = vi.hoisted(() => {
  const catalog = [
    { id: 1, name: 'Wood', resource_type: 'material', unit: 'board ft', is_active: true },
    { id: 2, name: 'Wood Glue', resource_type: 'material', unit: 'liter', is_active: true },
    { id: 3, name: 'Epoxy', resource_type: 'material', unit: 'liter', is_active: false },
  ]

  const updateResourceMock = vi.fn(
    async (id: number, data: Record<string, unknown>) => {
      const resource = catalog.find((candidate) => candidate.id === id)

      // Only reactivation affects the mock catalog's active flag -
      // other updates (e.g. the rename test) must not leak into
      // later tests.
      if (resource && data.is_active === true) {
        resource.is_active = true
      }

      return resource
    },
  )

  return { catalog, updateResourceMock }
})

vi.mock('./api/resourceApi', () => ({
  fetchResources: vi.fn(async () =>
    catalog.filter((resource) => resource.is_active),
  ),
  fetchAllResourcesIncludingInactive: vi.fn(async () => catalog),
  updateResource: updateResourceMock,
  deleteResource: vi.fn(),
}))

vi.mock('./api/cycleResourceApi', () => ({
  fetchCycleResources: vi.fn().mockResolvedValue([
    { id: 10, production_cycle_id: 1, resource_id: 1, available_quantity: '1000.0000', unit_price: '50.0000' },
  ]),
  createCycleResource: vi.fn(),
  updateCycleResource: vi.fn().mockResolvedValue({
    id: 10, production_cycle_id: 1, resource_id: 1, available_quantity: '700.0000', unit_price: '50.0000',
  }),
}))

const findDropdownOption = (text: string): HTMLElement => {
  const option = screen
    .getAllByText(text)
    .map((element) => element.closest('[role="option"]'))
    .find((candidate) => candidate !== null)

  if (!(option instanceof HTMLElement)) {
    throw new Error(`No dropdown option found for "${text}"`)
  }

  return option
}

const renderPage = () => {
  const queryClient = new QueryClient()

  return render(
    <MantineProvider>
      <Notifications />
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <ResourcesPage />
        </QueryClientProvider>
      </ThemeProvider>
    </MantineProvider>,
  )
}

describe('ResourcesPage resource-update notification', () => {
  beforeEach(() => {
    notifications.clean()
    vi.clearAllMocks()

    const epoxy = catalog.find((resource) => resource.id === 3)

    if (epoxy) {
      epoxy.is_active = false
    }
  })

  it('shows the re-optimization warning when available_quantity changes', async () => {
    renderPage()

    await waitFor(() => screen.getByText('Wood'))

    await userEvent.click(screen.getByLabelText('Edit Wood'))

    const quantityInput = await screen.findByLabelText('Available Quantity')
    await userEvent.clear(quantityInput)
    await userEvent.type(quantityInput, '700')

    await userEvent.click(screen.getByRole('button', { name: 'Save Changes' }))

    await waitFor(() => {
      expect(
        screen.getByText('Resource Updated — Re-optimization Required'),
      ).toBeInTheDocument()
    })
  })

  it('shows the plain updated notification when only the name changes', async () => {
    renderPage()

    await waitFor(() => screen.getByText('Wood'))

    await userEvent.click(screen.getByLabelText('Edit Wood'))

    const nameInput = await screen.findByRole('combobox', {
      name: 'Name',
    })
    await userEvent.clear(nameInput)
    await userEvent.type(nameInput, 'Pine')

    await userEvent.click(screen.getByRole('button', { name: 'Save Changes' }))

    await waitFor(() => {
      expect(screen.getByText('Resource Updated')).toBeInTheDocument()
    })
    expect(
      screen.queryByText('Resource Updated — Re-optimization Required'),
    ).not.toBeInTheDocument()
  })

  it('offers existing active and inactive resources in the add form', async () => {
    renderPage()

    await waitFor(() => screen.getByText('Wood'))

    await userEvent.click(
      screen.getByRole('button', { name: 'Add Resource' }),
    )

    const dialog = await screen.findByRole('dialog')

    expect(
      within(dialog).queryByText('Reactivate Existing'),
    ).not.toBeInTheDocument()

    await userEvent.click(
      within(dialog).getByRole('combobox', { name: 'Name' }),
    )

    const woodOption = findDropdownOption('Wood')
    const epoxyOption = findDropdownOption('Epoxy')

    expect(within(woodOption).getByText('Active')).toBeInTheDocument()
    expect(within(epoxyOption).getByText('Inactive')).toBeInTheDocument()

    // Selecting an inactive resource explains why it can't be added
    // and never submits (no reactivation, no second row).
    await userEvent.click(epoxyOption)

    expect(
      within(dialog).getByText(/inactive, so it can't be added/i),
    ).toBeInTheDocument()
    expect(
      within(dialog).getByRole('button', { name: 'Add Resource' }),
    ).toBeDisabled()
  })

  it('adds an existing catalog resource to the current cycle', async () => {
    vi.mocked(createCycleResource).mockResolvedValue({
      id: 11,
      production_cycle_id: 1,
      resource_id: 2,
      available_quantity: '40.0000',
      unit_price: '9.0000',
    })

    renderPage()

    await waitFor(() => screen.getByText('Wood'))

    await userEvent.click(
      screen.getByRole('button', { name: 'Add Resource' }),
    )

    const dialog = await screen.findByRole('dialog')

    // No arbitrary typed name: the only way to fill Name is selecting
    // an existing catalog resource.
    await userEvent.click(
      within(dialog).getByRole('combobox', { name: 'Name' }),
    )
    await userEvent.click(findDropdownOption('Wood Glue'))

    const quantityInput = within(dialog).getByLabelText(
      'Available Quantity',
    )
    await userEvent.clear(quantityInput)
    await userEvent.type(quantityInput, '40')

    const priceInput = within(dialog).getByLabelText('Unit Price')
    await userEvent.clear(priceInput)
    await userEvent.type(priceInput, '9')

    await userEvent.click(
      within(dialog).getByRole('button', { name: 'Add Resource' }),
    )

    await waitFor(() => {
      expect(createCycleResource).toHaveBeenCalledWith(1, {
        resource_id: 2,
        available_quantity: 40,
        unit_price: 9,
      })
    })

    await waitFor(() => {
      expect(screen.getByText('Resource Added')).toBeInTheDocument()
    })
  })

  it('updates cycle inventory when the selected resource already has it', async () => {
    renderPage()

    await waitFor(() => screen.getByText('Wood'))

    await userEvent.click(
      screen.getByRole('button', { name: 'Add Resource' }),
    )

    const dialog = await screen.findByRole('dialog')

    await userEvent.click(
      within(dialog).getByRole('combobox', { name: 'Name' }),
    )
    await userEvent.click(findDropdownOption('Wood'))

    const quantityInput = within(dialog).getByLabelText(
      'Available Quantity',
    )
    await userEvent.clear(quantityInput)
    await userEvent.type(quantityInput, '700')

    await userEvent.click(
      within(dialog).getByRole('button', { name: 'Save Changes' }),
    )

    await waitFor(() => {
      expect(updateCycleResource).toHaveBeenCalledWith(1, 1, {
        available_quantity: 700,
        unit_price: 50,
      })
    })

    await waitFor(() => {
      expect(
        screen.getByText('Resource Updated — Re-optimization Required'),
      ).toBeInTheDocument()
    })
  })

  it('lists inactive resources and reactivates the original record after confirmation', async () => {
    renderPage()

    await waitFor(() => screen.getByText('Wood'))

    await userEvent.click(
      screen.getByRole('radio', { name: /^inactive/i }),
    )

    // The inactive view lists only the soft-deleted resource, with a
    // badge that identifies it as inactive.
    expect(await screen.findByText('Epoxy')).toBeInTheDocument()
    expect(screen.getByText('Inactive')).toBeInTheDocument()
    expect(screen.queryByText('Wood Glue')).not.toBeInTheDocument()

    await userEvent.click(
      screen.getByLabelText(/reactivate epoxy/i),
    )

    const dialog = await screen.findByRole('dialog')

    expect(
      within(dialog).getByText(
        /existing product-resource requirements are kept/i,
      ),
    ).toBeInTheDocument()

    await userEvent.click(
      within(dialog).getByRole('button', {
        name: 'Reactivate Resource',
      }),
    )

    // Existing id, is_active only: no new Resource row, no category/
    // unit rewrite, and no CycleResource write that could change the
    // cycle's quantity or price.
    await waitFor(() => {
      expect(updateResourceMock).toHaveBeenCalledWith(3, {
        is_active: true,
      })
    })

    expect(createCycleResource).not.toHaveBeenCalled()
    expect(updateCycleResource).not.toHaveBeenCalled()

    await waitFor(() => {
      expect(
        screen.getByText('Resource Reactivated'),
      ).toBeInTheDocument()
    })

    // The inactive list refetches and no longer contains it.
    await waitFor(() => {
      expect(
        screen.getByText('No inactive resources.'),
      ).toBeInTheDocument()
    })

    // It is back in the active table and selectable as Active in the
    // Add Resource form's catalog select.
    await userEvent.click(
      screen.getByRole('radio', { name: /^active/i }),
    )

    expect(await screen.findByText('Epoxy')).toBeInTheDocument()

    await userEvent.click(
      screen.getByRole('button', { name: 'Add Resource' }),
    )

    // Wait for the Add form's own control rather than the modal
    // container - the just-closed confirmation can still be in the
    // DOM during its exit transition.
    const nameCombobox = await screen.findByRole('combobox', {
      name: 'Name',
    })

    await userEvent.click(nameCombobox)

    const epoxyOption = findDropdownOption('Epoxy')

    expect(within(epoxyOption).getByText('Active')).toBeInTheDocument()
  })

  it('does not reactivate until the confirmation is accepted', async () => {
    renderPage()

    await waitFor(() => screen.getByText('Wood'))

    await userEvent.click(
      screen.getByRole('radio', { name: /inactive/i }),
    )

    await screen.findByText('Epoxy')

    await userEvent.click(
      screen.getByLabelText(/reactivate epoxy/i),
    )

    const dialog = await screen.findByRole('dialog')

    await userEvent.click(
      within(dialog).getByRole('button', { name: 'Cancel' }),
    )

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    expect(updateResourceMock).not.toHaveBeenCalled()
    expect(screen.getByText('Epoxy')).toBeInTheDocument()
  })

  it('shows an error and keeps the resource inactive when reactivation fails', async () => {
    updateResourceMock.mockRejectedValueOnce(new Error('Request failed'))

    renderPage()

    await waitFor(() => screen.getByText('Wood'))

    await userEvent.click(
      screen.getByRole('radio', { name: /inactive/i }),
    )

    await screen.findByText('Epoxy')

    await userEvent.click(
      screen.getByLabelText(/reactivate epoxy/i),
    )

    const dialog = await screen.findByRole('dialog')

    await userEvent.click(
      within(dialog).getByRole('button', {
        name: 'Reactivate Resource',
      }),
    )

    expect(
      await within(dialog).findByText(
        'Unable to reactivate resource. Please try again.',
      ),
    ).toBeInTheDocument()

    expect(
      screen.queryByText('Resource Reactivated'),
    ).not.toBeInTheDocument()

    expect(
      within(dialog).getByRole('button', {
        name: 'Reactivate Resource',
      }),
    ).not.toBeDisabled()

    // The table row is still in the inactive view with its
    // Reactivate action - the failed PATCH did not revive it.
    expect(
      screen.getByLabelText('Reactivate Epoxy'),
    ).toBeInTheDocument()
  })

  it('prevents repeated submissions while reactivation is pending', async () => {
    let resolveReactivate: (
      value: (typeof catalog)[number] | undefined,
    ) => void = () => {}

    updateResourceMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveReactivate = resolve
        }),
    )

    renderPage()

    await waitFor(() => screen.getByText('Wood'))

    await userEvent.click(
      screen.getByRole('radio', { name: /inactive/i }),
    )

    await screen.findByText('Epoxy')

    await userEvent.click(
      screen.getByLabelText(/reactivate epoxy/i),
    )

    const dialog = await screen.findByRole('dialog')

    const confirmButton = within(dialog).getByRole('button', {
      name: 'Reactivate Resource',
    })

    await userEvent.dblClick(confirmButton)

    await waitFor(() => {
      expect(updateResourceMock).toHaveBeenCalledTimes(1)
    })

    expect(confirmButton).toBeDisabled()

    resolveReactivate(catalog[2])

    await waitFor(() => {
      expect(
        screen.getByText('Resource Reactivated'),
      ).toBeInTheDocument()
    })
  })
})

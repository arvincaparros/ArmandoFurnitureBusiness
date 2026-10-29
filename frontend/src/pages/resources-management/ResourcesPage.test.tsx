import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import { Notifications, notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AxiosError, AxiosHeaders } from 'axios'
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

const {
  catalog,
  updateResourceMock,
  createResourceMock,
  permanentlyDeleteResourceMock,
} = vi.hoisted(() => {
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

  // POST /api/resources. Appends to the mock catalog so the
  // invalidated 'resources-all' refetch really does include the new
  // row - the same path the selector reads.
  const createResourceMock = vi.fn(
    async (data: {
      name: string
      resource_type: string
      unit: string
    }) => {
      const created = {
        id: 99,
        name: data.name,
        resource_type: data.resource_type,
        unit: data.unit,
        is_active: true,
      }

      catalog.push(created)

      return created
    },
  )

  // DELETE /api/resources/{id}/permanent. Removes the row from the
  // mock catalog so the invalidated refetch really does drop it from
  // both the Inactive view and the Add Resource selector - the same
  // path a real permanent delete takes. The shared catalog is
  // restored in beforeEach so this never leaks into other tests.
  const permanentlyDeleteResourceMock = vi.fn(async (id: number) => {
    const index = catalog.findIndex(
      (candidate) => candidate.id === id,
    )

    if (index !== -1) {
      catalog.splice(index, 1)
    }
  })

  return {
    catalog,
    updateResourceMock,
    createResourceMock,
    permanentlyDeleteResourceMock,
  }
})

vi.mock('./api/resourceApi', () => ({
  fetchResources: vi.fn(async () =>
    catalog.filter((resource) => resource.is_active),
  ),
  fetchAllResourcesIncludingInactive: vi.fn(async () => catalog),
  createResource: createResourceMock,
  updateResource: updateResourceMock,
  deleteResource: vi.fn(),
  permanentlyDeleteResource: permanentlyDeleteResourceMock,
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
    } else {
      // The permanent-delete tests really do remove id 3 from the
      // shared catalog, so it is restored here rather than left
      // missing for whichever test runs next.
      catalog.push({
        id: 3,
        name: 'Epoxy',
        resource_type: 'material',
        unit: 'liter',
        is_active: false,
      })
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

  it('creates a new catalog resource and makes it selectable for the cycle', async () => {
    vi.mocked(createCycleResource).mockResolvedValueOnce({
      id: 12,
      production_cycle_id: 1,
      resource_id: 99,
      available_quantity: '300.0000',
      unit_price: '5.0000',
    })

    renderPage()

    await waitFor(() => screen.getByText('Wood'))

    await userEvent.click(
      screen.getByRole('button', { name: 'Add Resource' }),
    )

    const dialog = await screen.findByRole('dialog')

    await userEvent.click(
      within(dialog).getByRole('radio', { name: 'Create New' }),
    )

    await userEvent.type(
      within(dialog).getByLabelText('Name'),
      'Sandpaper',
    )

    const quantityInput = within(dialog).getByLabelText(
      'Available Quantity',
    )
    await userEvent.clear(quantityInput)
    await userEvent.type(quantityInput, '300')

    const priceInput = within(dialog).getByLabelText('Unit Price')
    await userEvent.clear(priceInput)
    await userEvent.type(priceInput, '5')

    await userEvent.click(
      within(dialog).getByRole('button', {
        name: 'Create Resource',
      }),
    )

    // The master catalog row is created once, with the entered fields.
    await waitFor(() => {
      expect(createResourceMock).toHaveBeenCalledWith({
        name: 'Sandpaper',
        resource_type: 'material',
        unit: 'board ft',
      })
    })

    // The cycle reuses the id the server assigned, so no second
    // resource record is involved.
    await waitFor(() => {
      expect(createCycleResource).toHaveBeenCalledWith(1, {
        resource_id: 99,
        available_quantity: 300,
        unit_price: 5,
      })
    })

    await waitFor(() => {
      expect(screen.getByText('Resource Added')).toBeInTheDocument()
    })

    // The invalidated catalog refetch offers it in the existing-
    // resource selector, alongside the resources that were already
    // there. Wait for the just-closed add modal to leave the DOM
    // first - its footer button still carries the "Add Resource"
    // label during the exit transition.
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    await userEvent.click(
      screen.getByRole('button', { name: 'Add Resource' }),
    )

    const reopened = await screen.findByRole('dialog')

    await userEvent.click(
      within(reopened).getByRole('combobox', { name: 'Name' }),
    )

    expect(findDropdownOption('Sandpaper')).toBeInTheDocument()
    expect(findDropdownOption('Wood')).toBeInTheDocument()
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

  // --- Permanent delete -------------------------------------------
  //
  // A different endpoint from the soft delete (DELETE /{id}/
  // permanent vs DELETE /{id}), offered only on inactive rows and
  // irreversible - so these cover that it is reachable where it
  // should be, unreachable where it shouldn't, gated behind a
  // confirmation, and that a refused delete explains itself.

  const openInactiveView = async () => {
    renderPage()

    await waitFor(() => screen.getByText('Wood'))

    await userEvent.click(
      screen.getByRole('radio', { name: /^inactive/i }),
    )

    await screen.findByText('Epoxy')
  }

  it('offers reactivate and permanent delete on an inactive resource', async () => {
    await openInactiveView()

    expect(
      screen.getByLabelText(/reactivate epoxy/i),
    ).toBeInTheDocument()

    expect(
      screen.getByLabelText(/delete epoxy permanently/i),
    ).toBeInTheDocument()
  })

  it('does not offer permanent delete on an active resource', async () => {
    renderPage()

    await waitFor(() => screen.getByText('Wood'))

    // The active row keeps its edit and (soft) delete actions, but
    // permanent deletion must never be reachable for it - the
    // backend refuses it with a 409 as well.
    expect(screen.getByLabelText('Edit Wood')).toBeInTheDocument()

    expect(
      screen.queryByLabelText(/delete wood permanently/i),
    ).not.toBeInTheDocument()
  })

  it('warns that deletion is irreversible and does nothing until confirmed', async () => {
    await openInactiveView()

    await userEvent.click(
      screen.getByLabelText(/delete epoxy permanently/i),
    )

    const dialog = await screen.findByRole('dialog')

    expect(
      within(dialog).getByText(/this cannot be undone/i),
    ).toBeInTheDocument()

    expect(
      within(dialog).getByText(
        /cannot be reactivated afterwards/i,
      ),
    ).toBeInTheDocument()

    expect(
      within(dialog).getByText(
        /utilization history is kept/i,
      ),
    ).toBeInTheDocument()

    await userEvent.click(
      within(dialog).getByRole('button', { name: 'Cancel' }),
    )

    expect(permanentlyDeleteResourceMock).not.toHaveBeenCalled()

    // Still listed, still inactive - cancelling changed nothing.
    expect(await screen.findByText('Epoxy')).toBeInTheDocument()
  })

  it('permanently deletes an inactive resource and refreshes the list', async () => {
    await openInactiveView()

    await userEvent.click(
      screen.getByLabelText(/delete epoxy permanently/i),
    )

    const dialog = await screen.findByRole('dialog')

    await userEvent.click(
      within(dialog).getByRole('button', {
        name: 'Delete Permanently',
      }),
    )

    await waitFor(() => {
      expect(permanentlyDeleteResourceMock).toHaveBeenCalledWith(3)
    })

    // Permanent delete only - the soft-delete endpoint and the
    // is_active PATCH used by reactivation are never touched.
    expect(updateResourceMock).not.toHaveBeenCalled()

    await waitFor(() => {
      expect(
        screen.getByText('Resource Permanently Deleted'),
      ).toBeInTheDocument()
    })

    // The list refetches and the row is gone from the Inactive view.
    await waitFor(() => {
      expect(
        screen.getByText('No inactive resources.'),
      ).toBeInTheDocument()
    })

    // Its name is free again, so it is no longer offered anywhere in
    // the Add Resource selector.
    await userEvent.click(
      screen.getByRole('radio', { name: /^active/i }),
    )

    await userEvent.click(
      screen.getByRole('button', { name: 'Add Resource' }),
    )

    const nameCombobox = await screen.findByRole('combobox', {
      name: 'Name',
    })

    await userEvent.click(nameCombobox)

    expect(screen.queryByText('Epoxy')).not.toBeInTheDocument()
  })

  it('surfaces the backend reason and keeps the resource when deletion is blocked', async () => {
    const detail =
      "'Epoxy' cannot be deleted permanently because it is still used by resource requirements on Dining Table. Remove those first."

    permanentlyDeleteResourceMock.mockRejectedValueOnce(
      new AxiosError(
        'Request failed with status code 409',
        'ERR_BAD_REQUEST',
        undefined,
        undefined,
        {
          status: 409,
          statusText: 'Conflict',
          data: { detail },
          headers: {},
          config: {
            headers: new AxiosHeaders(),
          },
        },
      ),
    )

    await openInactiveView()

    await userEvent.click(
      screen.getByLabelText(/delete epoxy permanently/i),
    )

    const dialog = await screen.findByRole('dialog')

    await userEvent.click(
      within(dialog).getByRole('button', {
        name: 'Delete Permanently',
      }),
    )

    // The 409's own detail is shown, not a generic failure message,
    // so the user knows exactly what to clear first.
    expect(
      await within(dialog).findByText(detail),
    ).toBeInTheDocument()

    expect(
      within(dialog).getByText(/deletion blocked/i),
    ).toBeInTheDocument()

    // The modal stays open and the resource is untouched.
    expect(
      within(dialog).getByRole('button', {
        name: 'Delete Permanently',
      }),
    ).toBeEnabled()

    expect(
      screen.queryByText('Resource Permanently Deleted'),
    ).not.toBeInTheDocument()

    expect(catalog.some((resource) => resource.id === 3)).toBe(true)
  })
})

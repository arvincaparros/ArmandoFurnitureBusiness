import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import { Notifications, notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ResourcesPage from './ResourcesPage'
import { ThemeProvider } from '../../theme/ThemeContext'

vi.mock('../../hooks/useLatestProductionCycle', () => ({
  default: () => ({ cycleId: 1, hasCycle: true, isLoading: false, isError: false }),
}))

vi.mock('./api/resourceApi', () => ({
  fetchResources: vi.fn().mockResolvedValue([
    { id: 1, name: 'Wood', resource_type: 'material', unit: 'board ft', is_active: true },
  ]),
  fetchAllResourcesIncludingInactive: vi.fn().mockResolvedValue([]),
  createResource: vi.fn(),
  updateResource: vi.fn().mockResolvedValue({ id: 1, name: 'Wood' }),
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
  })

  it('shows the re-optimization warning when available_quantity changes', async () => {
    renderPage()

    await waitFor(() => screen.getByText('Wood'))

    await userEvent.click(screen.getByLabelText(/edit wood/i))

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

    await userEvent.click(screen.getByLabelText(/edit wood/i))

    const nameInput = await screen.findByLabelText('Name')
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
})

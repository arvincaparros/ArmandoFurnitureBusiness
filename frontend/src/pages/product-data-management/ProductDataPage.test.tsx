import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ProductDataPage from './ProductDataPage'
import { updateProduct } from './api/productApi'
import { ThemeProvider } from '../../theme/ThemeContext'

vi.mock('../../hooks/useLatestProductionCycle', () => ({
  default: () => ({
    cycleId: 1,
    hasCycle: true,
    isLoading: false,
    isError: false,
  }),
}))

// Resource requirements are irrelevant to this test and would add
// their own per-product requests.
vi.mock('./components/ProductResourceRequirementsSection', () => ({
  default: () => <div data-testid="requirements-section" />,
}))

const { store, updateProductMock } = vi.hoisted(() => {
  const store = {
    products: [
      {
        id: 1,
        name: 'Ordinary Chair',
        selling_price: '3500.00',
        labor_cost: '300.00',
        minimum_demand: '3.0000',
        is_active: true,
      },
    ],
  }

  // PATCH /api/products/{id}. Writes through to the same store
  // fetchProducts reads, so the invalidated ['products'] refetch
  // really does return the new value - the actual path the table
  // re-renders from.
  const updateProductMock = vi.fn(
    async (id: number, data: Record<string, unknown>) => {
      const product = store.products.find(
        (candidate) => candidate.id === id,
      )!

      if (data.minimum_demand !== undefined) {
        product.minimum_demand = Number(
          data.minimum_demand,
        ).toFixed(4)
      }

      return product
    },
  )

  return { store, updateProductMock }
})

vi.mock('./api/productApi', () => ({
  fetchProducts: vi.fn(async () => store.products),
  createProduct: vi.fn(),
  updateProduct: updateProductMock,
  deleteProduct: vi.fn(),
}))

vi.mock('./api/productResourceApi', () => ({
  fetchAllResourcesForPicker: vi.fn(async () => []),
  fetchProductResourceRequirements: vi.fn(async () => []),
}))

vi.mock('./api/cycleResourceApi', () => ({
  fetchCycleResources: vi.fn(async () => []),
}))

const renderPage = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  render(
    <MantineProvider>
      <Notifications />
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <ProductDataPage />
        </QueryClientProvider>
      </ThemeProvider>
    </MantineProvider>,
  )
}

const rowFor = (name: string) =>
  screen.getByText(name).closest('tr') as HTMLElement

describe('ProductDataPage Minimum Demand editing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    store.products[0].minimum_demand = '3.0000'
  })

  it('shows the stored minimum demand in the table', async () => {
    renderPage()

    await waitFor(() => screen.getByText('Ordinary Chair'))

    expect(
      within(rowFor('Ordinary Chair')).getByText('3'),
    ).toBeInTheDocument()
  })

  it('saves an edited minimum demand and refreshes the table', async () => {
    renderPage()

    await waitFor(() => screen.getByText('Ordinary Chair'))

    // ProductRowActions renders unlabeled icon buttons (edit, then
    // delete) - selected positionally rather than by accessible name,
    // which that component does not currently provide.
    const [editButton] = within(
      rowFor('Ordinary Chair'),
    ).getAllByRole('button')

    await userEvent.click(editButton)

    const dialog = await screen.findByRole('dialog')

    const input = within(dialog).getByLabelText(
      'Minimum Demand',
    ) as HTMLInputElement

    expect(input).toHaveValue('3')

    await userEvent.clear(input)
    await userEvent.type(input, '7')

    await userEvent.click(
      within(dialog).getByRole('button', { name: 'Save Changes' }),
    )

    await waitFor(() =>
      expect(updateProduct).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ minimum_demand: 7 }),
      ),
    )

    // The table must reflect the new value after the mutation's
    // query invalidation refetches ['products'].
    await waitFor(() =>
      expect(
        within(rowFor('Ordinary Chair')).getByText('7'),
      ).toBeInTheDocument(),
    )
  })
})

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'

import AddProductModal from './AddProductModal'

import type { Product } from '../types'

// The Edit variant renders ProductResourceRequirementsSection, which
// runs its own queries - stubbed so these tests stay focused on the
// Minimum Demand field and never hit the network.
vi.mock('./ProductResourceRequirementsSection', () => ({
  default: () => <div data-testid="requirements-section" />,
}))

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: 1,
    productName: 'Ordinary Chair',
    sellingPrice: 3500,
    isActive: true,
    resourceQuantities: {},
    minimumDemand: 3,
    materialCost: 500,
    laborCost: 300,
    machineCost: 100,
    totalCost: 900,
    profit: 2600,
    ...overrides,
  }
}

const renderModal = (product: Product | null = null) => {
  const onSave = vi.fn().mockResolvedValue(undefined)

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  render(
    <MantineProvider>
      <QueryClientProvider client={queryClient}>
        <AddProductModal
          opened
          onClose={vi.fn()}
          onSave={onSave}
          product={product}
        />
      </QueryClientProvider>
    </MantineProvider>,
  )

  return { onSave }
}

const minimumDemandInput = () =>
  screen.getByLabelText('Minimum Demand') as HTMLInputElement

const saveButton = () =>
  screen.getByRole('button', { name: /Save Changes|Add Product/ })

describe('AddProductModal Minimum Demand field', () => {
  it('renders the field with its description', () => {
    renderModal()

    expect(minimumDemandInput()).toBeInTheDocument()
    expect(
      screen.getByText(
        'Minimum units the optimizer must produce per production cycle. 0 means no minimum.',
      ),
    ).toBeInTheDocument()
  })

  it('prefills the existing value when editing', () => {
    renderModal(makeProduct({ minimumDemand: 4 }))

    expect(minimumDemandInput()).toHaveValue('4')
  })

  it('prefills a stored 0 as 0 when editing', () => {
    renderModal(makeProduct({ minimumDemand: 0 }))

    expect(minimumDemandInput()).toHaveValue('0')
  })

  it('prefills the real value even when the cost breakdown is null', () => {
    renderModal(
      makeProduct({
        minimumDemand: 5,
        materialCost: null,
        laborCost: null,
        machineCost: null,
        totalCost: null,
        profit: null,
      }),
    )

    expect(minimumDemandInput()).toHaveValue('5')
  })

  it('defaults to 0 when creating', () => {
    renderModal(null)

    expect(minimumDemandInput()).toHaveValue('0')
  })

  it('includes minimum_demand in the save payload', async () => {
    const { onSave } = renderModal(makeProduct({ minimumDemand: 3 }))

    await userEvent.clear(minimumDemandInput())
    await userEvent.type(minimumDemandInput(), '7')

    await userEvent.click(saveButton())

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1))

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ minimum_demand: 7 }),
    )
  })

  it('sends an explicit 0 rather than omitting the field', async () => {
    const { onSave } = renderModal(makeProduct({ minimumDemand: 3 }))

    await userEvent.clear(minimumDemandInput())
    await userEvent.type(minimumDemandInput(), '0')

    await userEvent.click(saveButton())

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1))

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ minimum_demand: 0 }),
    )
  })

  it('blocks submission when the field is cleared', async () => {
    const { onSave } = renderModal(makeProduct({ minimumDemand: 3 }))

    await userEvent.clear(minimumDemandInput())

    expect(saveButton()).toBeDisabled()

    await userEvent.click(saveButton())

    expect(onSave).not.toHaveBeenCalled()
  })

  it('rejects a typed decimal point, keeping the value a whole number', async () => {
    const { onSave } = renderModal(makeProduct({ minimumDemand: 3 }))

    await userEvent.clear(minimumDemandInput())
    await userEvent.type(minimumDemandInput(), '2.5')

    // allowDecimal={false} drops the separator entirely rather than
    // producing a fractional value.
    expect(minimumDemandInput().value).not.toContain('.')

    await userEvent.click(saveButton())

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1))

    const payload = onSave.mock.calls[0][0] as {
      minimum_demand: number
    }

    expect(Number.isInteger(payload.minimum_demand)).toBe(true)
  })

  it('rejects a typed negative sign', async () => {
    renderModal(makeProduct({ minimumDemand: 3 }))

    await userEvent.clear(minimumDemandInput())
    await userEvent.type(minimumDemandInput(), '-5')

    // allowNegative={false} strips the sign.
    expect(minimumDemandInput().value).not.toContain('-')
  })
})

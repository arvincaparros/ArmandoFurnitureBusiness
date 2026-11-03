import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import { describe, expect, it, vi } from 'vitest'

import AddTransactionModal from './AddTransactionModal'

import type { Transaction } from '../types'
import type {
  ProductSummary,
  SalesTransactionCreateRequest,
  SalesTransactionUpdateRequest,
} from '../api/transactionTypes'

const products: ProductSummary[] = [
  {
    id: 1,
    name: 'Test Chair',
    selling_price: '1200.00',
  },
]

const existingTransaction: Transaction = {
  id: 7,
  productId: 1,
  transactionNumber: 'TRX-000007',
  date: '2026-09-01',
  furnitureProduct: 'Test Chair',
  quantityProduced: 5,
  quantitySold: 3,
  unitPrice: 1200,
  salesAmount: 3600,
  // Stored TOTAL (quantity produced x the per-unit rate the record
  // was saved with) - no longer editable through this form.
  productionCost: 2500,
  profitEarned: 1100,
}

interface RenderOptions {
  transaction?: Transaction | null
  onSave?: (
    data:
      | SalesTransactionCreateRequest
      | SalesTransactionUpdateRequest,
  ) => Promise<void>
  stockByProductId?: Record<number, number>
  producedByProductId?: Record<number, number>
  isStockValidationEnabled?: boolean
}

// Takes an options object since Task 15: the modal now requires the
// three inventory props, and the new cases vary them. The default is
// validation OFF with empty maps, which is exactly how the four
// pre-Task-15 tests behaved, so none of their expectations change.
const renderModal = ({
  transaction = null,
  onSave = vi.fn().mockResolvedValue(undefined),
  stockByProductId = {},
  producedByProductId = {},
  isStockValidationEnabled = false,
}: RenderOptions = {}) => {
  const onClose = vi.fn()

  const { rerender } = render(
    <MantineProvider>
      <AddTransactionModal
        opened
        products={products}
        transaction={transaction}
        stockByProductId={stockByProductId}
        producedByProductId={producedByProductId}
        isStockValidationEnabled={isStockValidationEnabled}
        onClose={onClose}
        onSave={onSave}
      />
    </MantineProvider>,
  )

  // Exposed so a test can simulate the page re-rendering the SAME
  // open modal with an updated inventory snapshot (e.g. after a sale
  // or an apply is recorded and GET /api/inventory is refetched) -
  // React preserves this component's state (like the selected
  // productId) across a rerender of the same element, exactly as it
  // would in the real app while the modal stays open.
  const rerenderWithProps = (
    overrides: RenderOptions = {},
  ) => {
    const merged = {
      transaction,
      onSave,
      stockByProductId,
      producedByProductId,
      isStockValidationEnabled,
      ...overrides,
    }

    rerender(
      <MantineProvider>
        <AddTransactionModal
          opened
          products={products}
          transaction={merged.transaction ?? null}
          stockByProductId={merged.stockByProductId}
          producedByProductId={merged.producedByProductId}
          isStockValidationEnabled={
            merged.isStockValidationEnabled
          }
          onClose={onClose}
          onSave={merged.onSave}
        />
      </MantineProvider>,
    )
  }

  return { onSave, onClose, rerenderWithProps }
}

const setNumber = async (label: string, value: string) => {
  const input = screen.getByLabelText(label)

  await userEvent.clear(input)
  await userEvent.type(input, value)
}

const selectProduct = async (name: string) => {
  await userEvent.click(
    screen.getByRole('combobox', {
      name: 'Furniture Product',
    }),
  )

  const option = screen
    .getAllByText(name)
    .map((element) => element.closest('[role="option"]'))
    .find((candidate) => candidate !== null)

  if (!(option instanceof HTMLElement)) {
    throw new Error(`Product option not found: ${name}`)
  }

  await userEvent.click(option)
}

describe('AddTransactionModal', () => {
  it('shows only the simplified fields and the sales summary', () => {
    renderModal()

    expect(screen.getByLabelText('Date')).toBeInTheDocument()
    expect(
      screen.getByRole('combobox', {
        name: 'Furniture Product',
      }),
    ).toBeInTheDocument()
    expect(
      screen.getByLabelText('Quantity Produced'),
    ).toBeInTheDocument()
    expect(
      screen.getByLabelText('Quantity Sold'),
    ).toBeInTheDocument()
    expect(
      screen.getByLabelText('Unit Price'),
    ).toBeInTheDocument()

    expect(
      screen.queryByLabelText('Production Cost / Unit'),
    ).not.toBeInTheDocument()

    expect(
      screen.getByText('Estimated Sales Amount'),
    ).toBeInTheDocument()
    expect(
      screen.queryByText('Estimated Production Cost'),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByText('Estimated Profit'),
    ).not.toBeInTheDocument()
  })

  it('previews only the estimated sales amount', async () => {
    renderModal()

    await setNumber('Quantity Sold', '2')
    await setNumber('Unit Price', '1000')

    expect(screen.getByText('₱2,000')).toBeInTheDocument()
  })

  it('still creates a transaction, submitting a zero per-unit production cost', async () => {
    const { onSave, onClose } = renderModal()

    // Nothing selected/entered yet - the form cannot be submitted.
    expect(
      screen.getByRole('button', { name: 'Save' }),
    ).toBeDisabled()

    await selectProduct('Test Chair')

    // Unit Price is auto-filled from the product's selling price
    // (Mantine renders the "₱ " prefix inside the input's display
    // value, so match the numeric part only).
    expect(
      (screen.getByLabelText('Unit Price') as HTMLInputElement)
        .value,
    ).toContain('1200')

    // Quantity Produced is read-only and server-filled now, so this
    // test no longer types into it.
    await setNumber('Quantity Sold', '3')

    const dateValue = (
      screen.getByLabelText('Date') as HTMLInputElement
    ).value

    await userEvent.click(
      screen.getByRole('button', { name: 'Save' }),
    )

    expect(onSave).toHaveBeenCalledWith({
      product_id: 1,
      transaction_date: `${dateValue}T00:00:00`,
      quantity: 3,
      unit_price: 1200,
      production_cost: 0,
    })
    expect(onClose).toHaveBeenCalled()
  })

  it('still edits a transaction and omits production cost so the stored cost is preserved', async () => {
    const { onSave, onClose } = renderModal({
      transaction: existingTransaction,
    })

    expect(
      screen.getByRole('combobox', {
        name: 'Furniture Product',
      }),
    ).toBeDisabled()

    await setNumber('Quantity Sold', '4')

    await userEvent.click(
      screen.getByRole('button', { name: 'Save' }),
    )

    // No product_id (the PATCH contract has no such field) and no
    // production_cost (omitted on purpose, so the backend keeps the
    // rate this transaction was saved with).
    expect(onSave).toHaveBeenCalledWith({
      transaction_date: '2026-09-01T00:00:00',
      quantity: 4,
      unit_price: 1200,
    })
    expect(onClose).toHaveBeenCalled()
  })

  // --- Task 15 -----------------------------------------------------
  // Quantity Produced is server-computed (a per-cycle drawdown) and
  // Quantity Sold is capped at available stock whenever a complete
  // opening balance has been reviewed. Both figures come from
  // GET /api/inventory; nothing is recomputed here.

  it('shows Quantity Produced as read-only and filled from the product\'s available production balance', async () => {
    // Quantity Produced must reflect available stock (opening + all
    // applied production - all sales, continuous), NOT
    // producedByProductId's per-cycle drawdown - the two are
    // deliberately different here (10 vs 15) to prove the field binds
    // to the correct one.
    renderModal({
      producedByProductId: { 1: 10 },
      stockByProductId: { 1: 15 },
      isStockValidationEnabled: true,
    })

    await selectProduct('Test Chair')

    const producedInput = screen.getByLabelText(
      /quantity produced/i,
    ) as HTMLInputElement

    expect(producedInput).toHaveAttribute('readonly')
    expect(producedInput.value).toBe('15')
  })

  it('displays the continuous available balance through an apply -> sell -> apply sequence (Apply 10 -> 10, sell 4 -> 6, apply 5 more -> 11)', async () => {
    // Step 1: Apply 10 units. Available balance is now 10.
    const { rerenderWithProps } = renderModal({
      stockByProductId: { 1: 10 },
      isStockValidationEnabled: true,
    })

    await selectProduct('Test Chair')

    expect(
      (
        screen.getByLabelText(
          /quantity produced/i,
        ) as HTMLInputElement
      ).value,
    ).toBe('10')

    // Step 2: Record a sale of 4. The backend ledger reduces available
    // stock to 6 (10 - 4); the page refetches GET /api/inventory and
    // re-renders this same open modal with the new snapshot.
    rerenderWithProps({ stockByProductId: { 1: 6 } })

    expect(
      (
        screen.getByLabelText(
          /quantity produced/i,
        ) as HTMLInputElement
      ).value,
    ).toBe('6')

    // Step 3: Apply another 5 units. The new apply ADDS to the
    // existing 6 (never replaces it) - available stock becomes 11.
    rerenderWithProps({ stockByProductId: { 1: 11 } })

    // Opening Add Transaction and selecting the product now must
    // display 11, exactly matching the approved example.
    expect(
      (
        screen.getByLabelText(
          /quantity produced/i,
        ) as HTMLInputElement
      ).value,
    ).toBe('11')
  })

  it('shows available stock for the selected product', async () => {
    renderModal({
      producedByProductId: { 1: 10 },
      stockByProductId: { 1: 15 },
      isStockValidationEnabled: true,
    })

    await selectProduct('Test Chair')

    expect(
      await screen.findByText(/15 units available/i),
    ).toBeInTheDocument()
  })

  it('blocks a quantity sold above available stock', async () => {
    const onSave = vi.fn()

    renderModal({
      onSave,
      producedByProductId: { 1: 10 },
      stockByProductId: { 1: 15 },
      isStockValidationEnabled: true,
    })

    await selectProduct('Test Chair')

    await userEvent.clear(screen.getByLabelText(/quantity sold/i))
    await userEvent.type(
      screen.getByLabelText(/quantity sold/i),
      '16',
    )

    expect(
      await screen.findByText(/only 15 units are available/i),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: /^save$/i }),
    ).toBeDisabled()

    expect(onSave).not.toHaveBeenCalled()
  })

  it('does not cap the quantity sold while validation is off', async () => {
    renderModal({
      producedByProductId: {},
      stockByProductId: {},
      isStockValidationEnabled: false,
    })

    await selectProduct('Test Chair')

    await userEvent.clear(screen.getByLabelText(/quantity sold/i))
    await userEvent.type(screen.getByLabelText(/quantity sold/i), '99')

    expect(
      screen.queryByText(/units are available/i),
    ).not.toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: /^save$/i }),
    ).toBeEnabled()
  })

  it('omits quantity_produced from the create payload', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined)

    renderModal({
      onSave,
      producedByProductId: { 1: 10 },
      stockByProductId: { 1: 15 },
      isStockValidationEnabled: true,
    })

    await selectProduct('Test Chair')

    await userEvent.clear(screen.getByLabelText(/quantity sold/i))
    await userEvent.type(screen.getByLabelText(/quantity sold/i), '3')

    await userEvent.click(
      screen.getByRole('button', { name: /^save$/i }),
    )

    await waitFor(() => {
      expect(onSave).toHaveBeenCalled()
    })

    expect(
      onSave.mock.calls[0][0],
    ).not.toHaveProperty('quantity_produced')
  })
})

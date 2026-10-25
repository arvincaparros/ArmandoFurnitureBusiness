import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import { describe, expect, it, vi } from 'vitest'

import AddTransactionModal from './AddTransactionModal'

import type { Transaction } from '../types'
import type { ProductSummary } from '../api/transactionTypes'

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

const renderModal = (transaction: Transaction | null = null) => {
  const onSave = vi.fn().mockResolvedValue(undefined)
  const onClose = vi.fn()

  render(
    <MantineProvider>
      <AddTransactionModal
        opened
        products={products}
        transaction={transaction}
        onClose={onClose}
        onSave={onSave}
      />
    </MantineProvider>,
  )

  return { onSave, onClose }
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

    await setNumber('Quantity Produced', '5')
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
      quantity_produced: 5,
      quantity: 3,
      unit_price: 1200,
      production_cost: 0,
    })
    expect(onClose).toHaveBeenCalled()
  })

  it('still edits a transaction and omits production cost so the stored cost is preserved', async () => {
    const { onSave, onClose } = renderModal(
      existingTransaction,
    )

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
      quantity_produced: 5,
      quantity: 4,
      unit_price: 1200,
    })
    expect(onClose).toHaveBeenCalled()
  })
})

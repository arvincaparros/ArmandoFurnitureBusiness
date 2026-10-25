import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import { describe, expect, it, vi } from 'vitest'

import TransactionTable from './TransactionTable'

import type { Transaction } from '../types'

const transactions: Transaction[] = [
  {
    id: 1,
    productId: 1,
    transactionNumber: 'TRX-000001',
    date: '2026-09-01',
    furnitureProduct: 'Test Chair',
    quantityProduced: 5,
    quantitySold: 3,
    unitPrice: 1200,
    salesAmount: 3600,
    productionCost: 2500,
    profitEarned: 1100,
  },
  {
    id: 2,
    productId: 2,
    transactionNumber: 'TRX-000002',
    date: '2026-09-02',
    furnitureProduct: 'Test Table',
    quantityProduced: 2,
    quantitySold: 1,
    unitPrice: 5000,
    salesAmount: 5000,
    productionCost: 4000,
    profitEarned: 1000,
  },
]

const renderTable = () => {
  const onEdit = vi.fn()
  const onDelete = vi.fn()
  const onSort = vi.fn()

  const view = render(
    <MantineProvider>
      <TransactionTable
        transactions={transactions}
        onEdit={onEdit}
        onDelete={onDelete}
        isLoading={false}
        isError={false}
        sortBy="date"
        reverse={false}
        onSort={onSort}
      />
    </MantineProvider>,
  )

  return { onEdit, onDelete, onSort, view }
}

describe('TransactionTable', () => {
  it('renders only the retained columns, in order', () => {
    renderTable()

    const headers = screen
      .getAllByRole('columnheader')
      .map((header) => header.textContent)

    expect(headers).toEqual([
      'Transaction #',
      'Date',
      'Furniture Product',
      'Quantity Produced',
      'Sold',
      'Sales',
      'Actions',
    ])

    expect(
      screen.queryByRole('columnheader', {
        name: 'Production Cost',
      }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('columnheader', {
        name: 'Profit Earned',
      }),
    ).not.toBeInTheDocument()
  })

  it('renders row values without production cost or profit', () => {
    renderTable()

    expect(screen.getByText('Test Chair')).toBeInTheDocument()
    expect(screen.getByText('₱3,600')).toBeInTheDocument()
    expect(screen.getByText('₱5,000')).toBeInTheDocument()

    // Stored cost/profit values from the fixtures never reach the UI.
    expect(screen.queryByText('₱2,500')).not.toBeInTheDocument()
    expect(screen.queryByText('₱1,100')).not.toBeInTheDocument()
    expect(screen.queryByText('₱4,000')).not.toBeInTheDocument()
    expect(screen.queryByText('₱1,000')).not.toBeInTheDocument()
  })

  it('keeps sorting and row actions working', async () => {
    const { onEdit, onDelete, onSort, view } = renderTable()

    await userEvent.click(
      screen.getByRole('columnheader', { name: /Sales/ }),
    )

    expect(onSort).toHaveBeenCalledWith('salesAmount')

    const editIcons =
      view.container.querySelectorAll('.lucide-pencil')
    const deleteIcons =
      view.container.querySelectorAll('.lucide-trash-2')

    expect(editIcons).toHaveLength(2)
    expect(deleteIcons).toHaveLength(2)

    await userEvent.click(
      editIcons[0].closest('button') as HTMLElement,
    )
    await userEvent.click(
      deleteIcons[1].closest('button') as HTMLElement,
    )

    expect(onEdit).toHaveBeenCalledWith(transactions[0])
    expect(onDelete).toHaveBeenCalledWith(
      transactions[1],
    )
  })
})

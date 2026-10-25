import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import TransactionHistoryPage from './TransactionHistoryPage'
import { ThemeProvider } from '../../theme/ThemeContext'

import useTransactions from './hooks/useTransactions'
import { exportCsv } from '../../utils/exportCsv'
import { exportExcel } from '../../utils/exportExcel'

import type { Transaction } from './types'

vi.mock('./hooks/useTransactions', () => ({
  default: vi.fn(),
}))

vi.mock('../../utils/exportCsv', () => ({
  exportCsv: vi.fn(),
}))

vi.mock('../../utils/exportExcel', () => ({
  exportExcel: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('../../utils/notify', () => ({
  notify: {
    exported: vi.fn(),
    added: vi.fn(),
    updated: vi.fn(),
    deleted: vi.fn(),
  },
}))

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

// The export maps are built from the page's own strongly-typed rows;
// these are the only columns the Export button may still emit.
const expectedExportHeaders = [
  'Transaction Number',
  'Date',
  'Furniture Product',
  'Quantity Produced',
  'Quantity Sold',
  'Sales Amount',
]

const renderPage = () => {
  vi.mocked(useTransactions).mockReturnValue({
    transactions,
    isLoading: false,
    isError: false,
    products: [],
    createTransaction: vi.fn(),
    isCreating: false,
    updateTransaction: vi.fn(),
    isUpdating: false,
    deleteTransaction: vi.fn(),
    isDeleting: false,
  } as unknown as ReturnType<typeof useTransactions>)

  render(
    <MantineProvider>
      <ThemeProvider>
        <TransactionHistoryPage />
      </ThemeProvider>
    </MantineProvider>,
  )
}

const openExportFormat = async (itemName: RegExp) => {
  await userEvent.click(
    screen.getByRole('button', { name: 'Export' }),
  )

  await userEvent.click(
    await screen.findByRole('menuitem', { name: itemName }),
  )
}

const expectSimplifiedRow = (
  row: Record<string, unknown>,
  expected: Record<string, unknown>,
) => {
  expect(Object.keys(row)).toEqual(
    expectedExportHeaders,
  )

  expect(row).not.toHaveProperty('Production Cost')
  expect(row).not.toHaveProperty('Profit Earned')

  expect(row).toMatchObject(expected)
}

describe('TransactionHistoryPage exports', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('exports CSV rows without production cost or profit earned', async () => {
    renderPage()

    await openExportFormat(/Export as CSV/i)

    expect(exportCsv).toHaveBeenCalledTimes(1)

    const [filename, rows] = vi.mocked(exportCsv).mock
      .calls[0]

    expect(filename).toBe('transaction-history')
    expect(rows).toHaveLength(2)

    expectSimplifiedRow(rows[0], {
      'Transaction Number': 'TRX-000001',
      Date: '2026-09-01',
      'Furniture Product': 'Test Chair',
      'Quantity Produced': 5,
      'Quantity Sold': 3,
      'Sales Amount': 3600,
    })
    expectSimplifiedRow(rows[1], {
      'Transaction Number': 'TRX-000002',
      Date: '2026-09-02',
      'Furniture Product': 'Test Table',
      'Quantity Produced': 2,
      'Quantity Sold': 1,
      'Sales Amount': 5000,
    })
  })

  it('exports Excel rows without production cost or profit earned', async () => {
    renderPage()

    await openExportFormat(/Export as Excel/i)

    await waitFor(() =>
      expect(exportExcel).toHaveBeenCalledTimes(1),
    )

    const [filename, rows, sheetName] = vi.mocked(
      exportExcel,
    ).mock.calls[0]

    expect(filename).toBe('transaction-history')
    // The page relies on exportExcel's default sheet name.
    expect(sheetName).toBeUndefined()
    expect(rows).toHaveLength(2)

    expectSimplifiedRow(rows[0], {
      'Transaction Number': 'TRX-000001',
      Date: '2026-09-01',
      'Furniture Product': 'Test Chair',
      'Quantity Produced': 5,
      'Quantity Sold': 3,
      'Sales Amount': 3600,
    })
    expectSimplifiedRow(rows[1], {
      'Transaction Number': 'TRX-000002',
      Date: '2026-09-02',
      'Furniture Product': 'Test Table',
      'Quantity Produced': 2,
      'Quantity Sold': 1,
      'Sales Amount': 5000,
    })
  })
})

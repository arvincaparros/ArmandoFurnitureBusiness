import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import TransactionHistoryPage from './TransactionHistoryPage'
import { ThemeProvider } from '../../theme/ThemeContext'

import useTransactions from './hooks/useTransactions'
import { exportCsv } from '../../utils/exportCsv'
import { exportExcel } from '../../utils/exportExcel'
import { notify } from '../../utils/notify'

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
    savedOutsideDateRange: vi.fn(),
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

// The window the SERVER resolved for the default view - the page
// never computes one itself, so the mock has to supply it the same
// way the real hook does.
const defaultRange = {
  startDate: '2026-09-01',
  endDate: '2026-09-02',
  mode: 'latest_available' as const,
}

const defaultAvailable = {
  earliest: '2026-08-01',
  latest: '2026-09-02',
}

const renderPage = (
  overrides: Record<string, unknown> = {},
) => {
  vi.mocked(useTransactions).mockReturnValue({
    transactions,
    range: defaultRange,
    available: defaultAvailable,
    total: transactions.length,
    isLoading: false,
    isError: false,
    products: [],
    createTransaction: vi.fn(),
    isCreating: false,
    updateTransaction: vi.fn(),
    isUpdating: false,
    deleteTransaction: vi.fn(),
    isDeleting: false,
    ...overrides,
  } as unknown as ReturnType<typeof useTransactions>)

  // env="test" is Mantine's own switch for disabling component
  // transitions in tests. Without it, Menu.Dropdown animates into a
  // portal and the two export assertions below fail intermittently -
  // raising the findBy timeout alone did not fix it, because on a bad
  // run the dropdown never mounted at all rather than mounting late.
  render(
    <MantineProvider env="test">
      <ThemeProvider>
        <TransactionHistoryPage />
      </ThemeProvider>
    </MantineProvider>,
  )
}

const lastFilterArg = () => {
  const calls = vi.mocked(useTransactions).mock.calls

  return calls[calls.length - 1][0]
}

const setDateInput = (label: string, value: string) => {
  fireEvent.change(screen.getByLabelText(label), {
    target: { value },
  })
}

const openExportFormat = async (itemName: RegExp) => {
  await userEvent.click(
    screen.getByRole('button', { name: 'Export' }),
  )

  // The transition that made this flaky is switched off by
  // MantineProvider env="test" in renderPage above; this longer
  // timeout is the remaining margin for the portal mounting under
  // parallel test load. Both are test-only - nothing in the
  // component needed to change.
  await userEvent.click(
    await screen.findByRole(
      'menuitem',
      { name: itemName },
      { timeout: 3000 },
    ),
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

describe('TransactionHistoryPage date range filter', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('asks the server for the default window without naming any dates', () => {
    renderPage()

    // The whole point of the server-resolved default: the page must
    // NOT synthesise a date range from the browser clock.
    expect(lastFilterArg()).toEqual({
      mode: 'latest_available',
    })
  })

  it('shows the window the server resolved', () => {
    renderPage()

    expect(
      screen.getByText(
        /most recent activity - 2026-09-01 to 2026-09-02/i,
      ),
    ).toBeInTheDocument()
  })

  it('reports the full span of recorded transactions', () => {
    renderPage()

    expect(
      screen.getByText(
        /Recorded transactions span 2026-08-01 to 2026-09-02/i,
      ),
    ).toBeInTheDocument()
  })

  it('requests the complete history when Show All is clicked', async () => {
    renderPage()

    fireEvent.click(
      screen.getByRole('button', { name: /Show All/i }),
    )

    await waitFor(() =>
      expect(lastFilterArg()).toEqual({ mode: 'all' }),
    )
  })

  it('sends both bounds for a custom range', async () => {
    renderPage()

    setDateInput('From', '2026-08-01')
    setDateInput('To', '2026-08-31')

    fireEvent.click(
      screen.getByRole('button', { name: 'Apply' }),
    )

    await waitFor(() =>
      expect(lastFilterArg()).toEqual({
        mode: 'custom',
        startDate: '2026-08-01',
        endDate: '2026-08-31',
      }),
    )
  })

  it('sends a one-sided range when only a start date is given', async () => {
    renderPage()

    setDateInput('From', '2026-08-01')

    fireEvent.click(
      screen.getByRole('button', { name: 'Apply' }),
    )

    await waitFor(() =>
      expect(lastFilterArg()).toEqual({
        mode: 'custom',
        startDate: '2026-08-01',
        endDate: undefined,
      }),
    )
  })

  it('refuses an end date earlier than the start date', () => {
    renderPage()

    setDateInput('From', '2026-08-31')
    setDateInput('To', '2026-08-01')

    expect(
      screen.getByText(
        /End date cannot be earlier than start date/i,
      ),
    ).toBeInTheDocument()

    // Blocked before the request is made - the backend's 400 is a
    // backstop, not the user-facing path.
    expect(
      screen.getByRole('button', { name: 'Apply' }),
    ).toBeDisabled()

    expect(lastFilterArg()).toEqual({
      mode: 'latest_available',
    })
  })

  it('cannot apply an empty range', () => {
    renderPage()

    expect(
      screen.getByRole('button', { name: 'Apply' }),
    ).toBeDisabled()
  })

  it('distinguishes an empty table from an empty range', () => {
    renderPage({
      transactions: [],
      total: 0,
      range: null,
      available: null,
    })

    // The table points at the recoverable action...
    expect(
      screen.getByText(
        /Use Add Transaction to record the first one/i,
      ),
    ).toBeInTheDocument()

    // ...and the header says there is no window, rather than naming
    // a range that filtered nothing out.
    expect(
      screen.getByText(
        /0 transactions - no transactions recorded yet/i,
      ),
    ).toBeInTheDocument()

    // Nothing here may suggest a range is hiding data.
    expect(
      screen.queryByText(/Use Show All/i),
    ).not.toBeInTheDocument()
  })

  it('offers Show All when the chosen range is empty', () => {
    renderPage({
      transactions: [],
      total: 0,
      range: {
        startDate: '2026-01-01',
        endDate: '2026-01-31',
        mode: 'custom' as const,
      },
    })

    expect(
      screen.getByText(
        /No transactions in the selected date range/i,
      ),
    ).toBeInTheDocument()

    expect(
      screen.getByText(/2026-01-01 to 2026-01-31/i),
    ).toBeInTheDocument()
  })

  it('keeps search working inside the returned window', async () => {
    renderPage()

    fireEvent.change(
      screen.getByPlaceholderText('Search transactions...'),
      { target: { value: 'Chair' } },
    )

    await waitFor(() => {
      expect(screen.getByText('Test Chair')).toBeInTheDocument()
      expect(
        screen.queryByText('Test Table'),
      ).not.toBeInTheDocument()
    })

    // Search is still client-side over the window: narrowing it must
    // not re-request anything from the server.
    expect(lastFilterArg()).toEqual({
      mode: 'latest_available',
    })
  })
})

describe('TransactionHistoryPage saving outside the active range', () => {
  const product = {
    id: 1,
    name: 'Test Chair',
    selling_price: '1200.00',
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  const applyCustomRange = async () => {
    setDateInput('From', '2026-09-01')
    setDateInput('To', '2026-09-30')

    fireEvent.click(
      screen.getByRole('button', { name: 'Apply' }),
    )

    await waitFor(() =>
      expect(lastFilterArg()).toEqual({
        mode: 'custom',
        startDate: '2026-09-01',
        endDate: '2026-09-30',
      }),
    )
  }

  const saveTransactionDated = async (isoDate: string) => {
    await userEvent.click(
      screen.getByRole('button', { name: /Add Transaction/i }),
    )

    const modal = await screen.findByRole('dialog')

    fireEvent.change(
      await within(modal).findByLabelText('Date'),
      { target: { value: isoDate } },
    )

    // Same approach AddTransactionModal.test.tsx already uses for
    // this Select: Mantine renders options into a portal, and only
    // the inner text node carries the label.
    await userEvent.click(
      within(modal).getByRole('combobox', {
        name: 'Furniture Product',
      }),
    )

    const option = screen
      .getAllByText(product.name)
      .map((element) => element.closest('[role="option"]'))
      .find((candidate) => candidate !== null)

    if (!(option instanceof HTMLElement)) {
      throw new Error(
        `Product option not found: ${product.name}`,
      )
    }

    await userEvent.click(option)

    fireEvent.change(
      within(modal).getByLabelText('Quantity Produced'),
      { target: { value: '5' } },
    )

    fireEvent.change(
      within(modal).getByLabelText('Quantity Sold'),
      { target: { value: '3' } },
    )

    await userEvent.click(
      within(modal).getByRole('button', { name: 'Save' }),
    )
  }

  it('warns that a saved transaction falls outside the chosen range', async () => {
    const createTransaction = vi.fn().mockResolvedValue({
      product_id: product.id,
    })

    renderPage({ products: [product], createTransaction })

    await applyCustomRange()
    await saveTransactionDated('2026-12-25')

    await waitFor(() =>
      expect(createTransaction).toHaveBeenCalledTimes(1),
    )

    // The save itself is still reported as a success...
    expect(notify.added).toHaveBeenCalledWith('Transaction')

    // ...and separately, that it is not in view.
    expect(
      notify.savedOutsideDateRange,
    ).toHaveBeenCalledWith('Transaction', '2026-12-25')
  })

  it('leaves the chosen range exactly as the user set it', async () => {
    const createTransaction = vi.fn().mockResolvedValue({
      product_id: product.id,
    })

    renderPage({ products: [product], createTransaction })

    await applyCustomRange()
    await saveTransactionDated('2026-12-25')

    await waitFor(() =>
      expect(createTransaction).toHaveBeenCalledTimes(1),
    )

    // Explicitly NOT widened to reveal the new row - the filter the
    // user chose survives the save untouched.
    expect(lastFilterArg()).toEqual({
      mode: 'custom',
      startDate: '2026-09-01',
      endDate: '2026-09-30',
    })

    expect(screen.getByLabelText('From')).toHaveValue(
      '2026-09-01',
    )
    expect(screen.getByLabelText('To')).toHaveValue(
      '2026-09-30',
    )
  })

  it('stays quiet when the saved date is inside the chosen range', async () => {
    const createTransaction = vi.fn().mockResolvedValue({
      product_id: product.id,
    })

    renderPage({ products: [product], createTransaction })

    await applyCustomRange()
    await saveTransactionDated('2026-09-15')

    await waitFor(() =>
      expect(createTransaction).toHaveBeenCalledTimes(1),
    )

    expect(notify.added).toHaveBeenCalledWith('Transaction')
    expect(
      notify.savedOutsideDateRange,
    ).not.toHaveBeenCalled()
  })

  it('stays quiet in the default window, where the server decides', async () => {
    const createTransaction = vi.fn().mockResolvedValue({
      product_id: product.id,
    })

    renderPage({ products: [product], createTransaction })

    // No custom range applied - the window is resolved server-side
    // after the refetch, so the client must not guess at visibility.
    await saveTransactionDated('1999-01-01')

    await waitFor(() =>
      expect(createTransaction).toHaveBeenCalledTimes(1),
    )

    expect(
      notify.savedOutsideDateRange,
    ).not.toHaveBeenCalled()
  })
})

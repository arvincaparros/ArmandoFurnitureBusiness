import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import OpeningInventoryPage from './OpeningInventoryPage'
import {
  fetchOpeningInventoryStatus,
  reviewOpeningInventorySet,
} from './api/openingInventoryApi'
import { ThemeProvider } from '../../theme/ThemeContext'

vi.mock('./api/openingInventoryApi', () => ({
  fetchOpeningInventorySets: vi.fn().mockResolvedValue([]),
  fetchOpeningInventoryStatus: vi.fn(),
  createOpeningInventorySet: vi.fn().mockResolvedValue({ id: 1 }),
  updateOpeningInventorySet: vi.fn().mockResolvedValue({ id: 1 }),
  reviewOpeningInventorySet: vi.fn().mockResolvedValue({}),
}))

vi.mock('../transaction-history/api/transactionApi', () => ({
  fetchProductSummaries: vi.fn().mockResolvedValue([
    { id: 1, name: 'Ordinary Table', selling_price: '2500.00' },
  ]),
}))

const mockStatus = vi.mocked(fetchOpeningInventoryStatus)
const mockReview = vi.mocked(reviewOpeningInventorySet)

const renderPage = (
  overrides: Record<string, unknown> = {},
) => {
  mockStatus.mockResolvedValue({
    stock_validation_enabled: false,
    reviewed_set: null,
    draft_set: null,
    ...overrides,
  } as never)

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <MantineProvider>
          <OpeningInventoryPage />
        </MantineProvider>
      </ThemeProvider>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mockReview.mockResolvedValue({} as never)
})

describe('OpeningInventoryPage', () => {
  // The asserted phrase is "cannot be recorded yet", not the plan's
  // original "not yet enforced": sales are REFUSED (409) until a
  // complete set is reviewed (Task 23 / Amendment A), so the banner
  // states that rather than claiming sales are recorded unvalidated.
  it('warns that sales are refused until a set is reviewed', async () => {
    renderPage()

    expect(
      await screen.findByText(/cannot be recorded yet/i),
    ).toBeInTheDocument()
  })

  it('lists every active product as a declarable row', async () => {
    renderPage()

    expect(
      await screen.findByText('Ordinary Table'),
    ).toBeInTheDocument()
  })

  it('requires confirmation before reviewing', async () => {
    renderPage({
      draft_set: {
        id: 1,
        set_number: 'OI-0001',
        status: 'DRAFT',
        effective_date: '2026-10-30T00:00:00',
        notes: null,
        created_at: '2026-10-30T00:00:00',
        reviewed_at: null,
        created_by_username: 'arvin',
        reviewed_by_username: null,
        items: [
          { id: 1, product_id: 1, quantity: '8.0000', notes: null },
        ],
      },
    })

    await userEvent.click(
      await screen.findByRole('button', { name: /mark as reviewed/i }),
    )

    expect(
      await screen.findByText(/cannot be edited afterwards/i),
    ).toBeInTheDocument()

    expect(mockReview).not.toHaveBeenCalled()

    await userEvent.click(
      screen.getByRole('button', { name: /^confirm review$/i }),
    )

    await waitFor(() => {
      expect(mockReview).toHaveBeenCalledWith(1)
    })
  })
})

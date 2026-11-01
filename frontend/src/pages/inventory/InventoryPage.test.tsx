import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

import InventoryPage from './InventoryPage'
import { ThemeProvider } from '../../theme/ThemeContext'

vi.mock('./api/inventoryApi', () => ({
  fetchInventory: vi.fn().mockResolvedValue({
    cycle_id: 3,
    cycle_start_date: '2026-10-25T00:00:00',
    cycle_end_date: '2026-11-01T00:00:00',
    stock_validation_enabled: true,
    products: [
      {
        product_id: 1,
        product_name: 'Ordinary Table',
        opening_quantity: '4.0000',
        total_produced: '20.0000',
        total_sold: '9.0000',
        available_stock: '15.0000',
        cycle_produced: '20.0000',
        cycle_sold: '9.0000',
      },
    ],
  }),
}))

const renderPage = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <MantineProvider>
          <MemoryRouter>
            <InventoryPage />
          </MemoryRouter>
        </MantineProvider>
      </ThemeProvider>
    </QueryClientProvider>,
  )
}

describe('InventoryPage', () => {
  it('shows cycle produced, cycle sold and available stock as separate columns', async () => {
    renderPage()

    expect(
      await screen.findByText('Ordinary Table'),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('columnheader', { name: /produced this cycle/i }),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('columnheader', { name: /sold this cycle/i }),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('columnheader', { name: /available stock/i }),
    ).toBeInTheDocument()
  })

  it('labels available stock as spanning all cycles', async () => {
    renderPage()

    expect(
      await screen.findByText(/across all cycles/i),
    ).toBeInTheDocument()
  })
})

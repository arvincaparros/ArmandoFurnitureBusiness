import { render, screen, waitFor } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ResourceUtilizationReportPage from './ResourceUtilizationReportPage'
import { ThemeProvider } from '../../theme/ThemeContext'
import { fetchResourceUtilization } from './api/utilizationApi'
import {
  fetchFeasibility,
  fetchProductionAllocations,
} from './api/productionAllocationApi'

vi.mock('../../hooks/useLatestProductionCycle', () => ({
  default: () => ({ cycleId: 1, hasCycle: true, isLoading: false, isError: false }),
}))

vi.mock('./api/utilizationApi', () => ({
  fetchResourceUtilization: vi.fn(),
}))

vi.mock('./api/productionAllocationApi', () => ({
  fetchProductionAllocations: vi.fn(),
  fetchFeasibility: vi.fn(),
}))

const emptyUtilizationResponse = {
  cycle_id: 1,
  overall_utilization_rate: '0',
  total_raw_materials_consumed: '0',
  total_labor_hours_used: '0',
  total_labor_hours_capacity: '0',
  total_machine_hours_used: '0',
  total_machine_hours_capacity: '0',
  material_resource_count: 0,
  most_constrained_resource: null,
  at_risk_resources: [],
  resources: [],
  bottlenecks: [],
}

const oneAppliedAllocation = [
  {
    id: 1,
    production_cycle_id: 1,
    product_id: 1,
    quantity: '12',
  },
]

beforeEach(() => {
  vi.mocked(fetchResourceUtilization).mockReset()
  vi.mocked(fetchProductionAllocations).mockReset()
  vi.mocked(fetchFeasibility).mockReset()

  vi.mocked(fetchResourceUtilization).mockResolvedValue(
    emptyUtilizationResponse,
  )
  vi.mocked(fetchProductionAllocations).mockResolvedValue(
    oneAppliedAllocation,
  )
})

const renderPage = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        // Deterministic, fast error states - the default retry
        // (3 attempts with backoff) would otherwise make the
        // feasibility-error test wait several seconds past
        // waitFor's default timeout before isError ever becomes
        // true.
        retry: false,
      },
    },
  })

  return render(
    <MantineProvider>
      <Notifications />
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <ResourceUtilizationReportPage />
          </MemoryRouter>
        </QueryClientProvider>
      </ThemeProvider>
    </MantineProvider>,
  )
}

describe('ResourceUtilizationReportPage feasibility warning', () => {
  it('shows a red Needs Review - Resource Shortage warning when the applied allocation exceeds capacity', async () => {
    vi.mocked(fetchFeasibility).mockResolvedValue({
      cycle_id: 1,
      is_feasible: false,
      bottlenecks: [
        { resource_id: 1, resource_name: 'Wood', unit: 'board ft', shortage_quantity: '189' },
      ],
      needs_reoptimization: true,
      applied_at: '2026-10-13T01:00:00',
    })

    renderPage()

    await waitFor(() => {
      expect(
        screen.getByText('Needs Review — Resource Shortage'),
      ).toBeInTheDocument()
    })

    expect(screen.getByText(/wood/i)).toBeInTheDocument()
    expect(screen.getByText(/189/)).toBeInTheDocument()
    expect(screen.getByText(/board ft/)).toBeInTheDocument()
    expect(
      screen.getByText(/last applied production allocation/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/not a newly generated optimization preview/i),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /go to production allocation/i }),
    ).toBeInTheDocument()
  })

  it('shows an orange Needs Re-optimization warning with no shortage text when still feasible but stale', async () => {
    vi.mocked(fetchFeasibility).mockResolvedValue({
      cycle_id: 1,
      is_feasible: true,
      bottlenecks: [],
      needs_reoptimization: true,
      applied_at: '2026-10-13T01:00:00',
    })

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Needs Re-optimization')).toBeInTheDocument()
    })

    expect(screen.queryByText(/short by/i)).not.toBeInTheDocument()
    expect(screen.queryByText('Needs Review — Resource Shortage')).not.toBeInTheDocument()
  })

  it('shows no feasibility warning when the applied allocation is feasible and unchanged', async () => {
    vi.mocked(fetchFeasibility).mockResolvedValue({
      cycle_id: 1,
      is_feasible: true,
      bottlenecks: [],
      needs_reoptimization: false,
      applied_at: '2026-10-13T01:00:00',
    })

    renderPage()

    await waitFor(() => {
      expect(fetchFeasibility).toHaveBeenCalled()
    })

    expect(screen.queryByText('Needs Re-optimization')).not.toBeInTheDocument()
    expect(
      screen.queryByText('Needs Review — Resource Shortage'),
    ).not.toBeInTheDocument()
  })

  it('shows no feasibility warning when no production allocation has been applied yet', async () => {
    vi.mocked(fetchProductionAllocations).mockResolvedValue([])
    vi.mocked(fetchFeasibility).mockResolvedValue({
      cycle_id: 1,
      is_feasible: true,
      bottlenecks: [],
      needs_reoptimization: false,
      applied_at: null,
    })

    renderPage()

    await waitFor(() => {
      expect(
        screen.getByText(/no production allocation has been applied/i),
      ).toBeInTheDocument()
    })

    expect(screen.queryByText('Needs Re-optimization')).not.toBeInTheDocument()
    expect(
      screen.queryByText('Needs Review — Resource Shortage'),
    ).not.toBeInTheDocument()
  })

  it('handles a null applied_at safely without crashing or showing a date', async () => {
    vi.mocked(fetchFeasibility).mockResolvedValue({
      cycle_id: 1,
      is_feasible: false,
      bottlenecks: [],
      needs_reoptimization: true,
      applied_at: null,
    })

    renderPage()

    await waitFor(() => {
      expect(
        screen.getByText('Needs Review — Resource Shortage'),
      ).toBeInTheDocument()
    })

    expect(screen.queryByText(/applied on/i)).not.toBeInTheDocument()
  })

  it('shows a neutral notice, not a false all-clear, when the feasibility check itself fails', async () => {
    vi.mocked(fetchFeasibility).mockRejectedValue(new Error('network error'))

    renderPage()

    await waitFor(() => {
      expect(
        screen.getByText(/unable to confirm whether this allocation needs re-optimization/i),
      ).toBeInTheDocument()
    })

    expect(screen.queryByText('Needs Re-optimization')).not.toBeInTheDocument()
    expect(
      screen.queryByText('Needs Review — Resource Shortage'),
    ).not.toBeInTheDocument()
  })
})

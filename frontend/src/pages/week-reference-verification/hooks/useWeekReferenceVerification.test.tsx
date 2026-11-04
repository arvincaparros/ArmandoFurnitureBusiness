import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi, beforeEach } from 'vitest'

import useWeekReferenceVerification from './useWeekReferenceVerification'
import {
  compareWeekReference,
  listWeekReferences,
} from '../api/weekReferenceApi'

vi.mock('../api/weekReferenceApi', () => ({
  listWeekReferences: vi.fn(),
  compareWeekReference: vi.fn(),
}))

function renderWithQueryClient() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return renderHook(() => useWeekReferenceVerification(), {
    wrapper: ({ children }) => (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    ),
  })
}

describe('useWeekReferenceVerification', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(listWeekReferences).mockResolvedValue([
      {
        week: 1,
        is_verified: true,
        resources: {
          wood: { available: '1000.0000', consumed: '821.0000', unit: 'bf', name: 'Wood' },
        },
        reference_allocation: { ordinary_chair: 10 },
        reference_total: 40,
        reference_profit: '102236.8148',
      },
    ])
  })

  it('loads the week list on mount and selects week 1 by default', async () => {
    const { result } = renderWithQueryClient()

    await waitFor(() => expect(result.current.weeks).toHaveLength(1))
    expect(result.current.selectedWeek).toBe(1)
    expect(result.current.currentWeek?.week).toBe(1)
  })

  it('runs the comparison with no overrides when none were set', async () => {
    vi.mocked(compareWeekReference).mockResolvedValue({
      week: 1,
      is_modified_input: false,
      reference_match_status: 'EXACT_MATCH',
      resources_used: {},
      resource_usage: {},
      status: 'Optimal',
      computed_allocation: {},
      reference_allocation: {},
      allocation_difference: {},
      allocation_matches_reference: true,
      computed_total: 40,
      reference_total: 40,
      computed_profit: '102237.16',
      reference_profit: '102236.8148',
      profit_matches_reference: true,
    })

    const { result } = renderWithQueryClient()
    await waitFor(() => expect(result.current.weeks).toHaveLength(1))

    await act(async () => {
      await result.current.runComparison()
    })

    expect(compareWeekReference).toHaveBeenCalledWith(1, undefined)
    await waitFor(() =>
      expect(result.current.result?.reference_match_status).toBe(
        'EXACT_MATCH',
      ),
    )
  })

  it('passes resource overrides through to the comparison call', async () => {
    vi.mocked(compareWeekReference).mockResolvedValue({
      week: 1,
      is_modified_input: true,
      reference_match_status: 'MODIFIED_INPUT',
      resources_used: {},
      resource_usage: {},
      status: 'Optimal',
      computed_allocation: {},
      reference_allocation: {},
      allocation_difference: {},
      allocation_matches_reference: false,
      computed_total: 0,
      reference_total: 40,
      computed_profit: '0',
      reference_profit: '102236.8148',
      profit_matches_reference: false,
    })

    const { result } = renderWithQueryClient()
    await waitFor(() => expect(result.current.weeks).toHaveLength(1))

    act(() => {
      result.current.setResourceOverride('doorknob', 0)
    })

    await act(async () => {
      await result.current.runComparison()
    })

    expect(compareWeekReference).toHaveBeenCalledWith(1, { doorknob: 0 })
    await waitFor(() =>
      expect(result.current.result?.is_modified_input).toBe(true),
    )
  })

  it('resets overrides when a different week is selected', async () => {
    const { result } = renderWithQueryClient()
    await waitFor(() => expect(result.current.weeks).toHaveLength(1))

    act(() => {
      result.current.setResourceOverride('doorknob', 0)
    })
    expect(result.current.resourceOverrides).toEqual({ doorknob: 0 })

    act(() => {
      result.current.selectWeek(2)
    })

    expect(result.current.selectedWeek).toBe(2)
    expect(result.current.resourceOverrides).toEqual({})
  })
})

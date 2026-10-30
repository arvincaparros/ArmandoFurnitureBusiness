import { describe, expect, it } from 'vitest'

import { toTransactionQueryParams } from './transactionApi'
import {
  toUiAvailableRange,
  toUiDateRange,
} from './transactionAdapter'

import { DEFAULT_TRANSACTION_FILTER } from '../types'

describe('toTransactionQueryParams', () => {
  it('sends no params for the default window', () => {
    // The server resolves the latest-available window itself. If the
    // client ever started sending dates here, the default view would
    // silently become clock-dependent again.
    expect(
      toTransactionQueryParams(DEFAULT_TRANSACTION_FILTER),
    ).toEqual({})
  })

  it('asks for the full history explicitly', () => {
    expect(toTransactionQueryParams({ mode: 'all' })).toEqual({
      show_all: 'true',
    })
  })

  it('sends both bounds of a custom range', () => {
    expect(
      toTransactionQueryParams({
        mode: 'custom',
        startDate: '2026-08-01',
        endDate: '2026-08-31',
      }),
    ).toEqual({
      start_date: '2026-08-01',
      end_date: '2026-08-31',
    })
  })

  it('omits an absent bound rather than sending it empty', () => {
    // FastAPI rejects "" as a date with a 422, so an omitted bound
    // must be absent from the query string entirely.
    expect(
      toTransactionQueryParams({
        mode: 'custom',
        startDate: '2026-08-01',
      }),
    ).toEqual({ start_date: '2026-08-01' })

    expect(
      toTransactionQueryParams({
        mode: 'custom',
        endDate: '2026-08-31',
      }),
    ).toEqual({ end_date: '2026-08-31' })
  })

  it('treats empty strings as absent bounds', () => {
    expect(
      toTransactionQueryParams({
        mode: 'custom',
        startDate: '',
        endDate: '',
      }),
    ).toEqual({})
  })
})

describe('transaction range adapters', () => {
  it('maps a resolved window to the UI shape', () => {
    expect(
      toUiDateRange({
        start_date: '2026-09-05',
        end_date: '2026-10-14',
        mode: 'latest_available',
      }),
    ).toEqual({
      startDate: '2026-09-05',
      endDate: '2026-10-14',
      mode: 'latest_available',
    })
  })

  it('preserves an open bound as null', () => {
    expect(
      toUiDateRange({
        start_date: '2026-09-05',
        end_date: null,
        mode: 'custom',
      }),
    ).toEqual({
      startDate: '2026-09-05',
      endDate: null,
      mode: 'custom',
    })
  })

  it('passes through a null window', () => {
    // Show All, or an empty table - neither has a window.
    expect(toUiDateRange(null)).toBeNull()
  })

  it('maps and passes through the available span', () => {
    expect(
      toUiAvailableRange({
        earliest: '2026-08-23',
        latest: '2026-10-14',
      }),
    ).toEqual({
      earliest: '2026-08-23',
      latest: '2026-10-14',
    })

    expect(toUiAvailableRange(null)).toBeNull()
  })
})

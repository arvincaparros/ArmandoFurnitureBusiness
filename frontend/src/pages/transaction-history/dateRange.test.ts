import { describe, expect, it } from 'vitest'

import { isDateOutsideFilter, toSubmittedDate } from './dateRange'
import { DEFAULT_TRANSACTION_FILTER } from './types'

const customRange = {
  mode: 'custom' as const,
  startDate: '2026-09-01',
  endDate: '2026-09-30',
}

describe('isDateOutsideFilter', () => {
  it('treats both endpoints of a custom range as inside', () => {
    expect(
      isDateOutsideFilter(customRange, '2026-09-01'),
    ).toBe(false)

    expect(
      isDateOutsideFilter(customRange, '2026-09-30'),
    ).toBe(false)
  })

  it('accepts a date within the range', () => {
    expect(
      isDateOutsideFilter(customRange, '2026-09-15'),
    ).toBe(false)
  })

  it('flags a date before the start', () => {
    expect(
      isDateOutsideFilter(customRange, '2026-08-31'),
    ).toBe(true)
  })

  it('flags a date after the end', () => {
    expect(
      isDateOutsideFilter(customRange, '2026-10-01'),
    ).toBe(true)
  })

  it('respects an open end bound', () => {
    const openEnd = {
      mode: 'custom' as const,
      startDate: '2026-09-01',
    }

    expect(isDateOutsideFilter(openEnd, '2026-08-31')).toBe(true)
    // Nothing after the start can be out of range when there is no
    // end bound at all.
    expect(isDateOutsideFilter(openEnd, '2027-12-31')).toBe(false)
  })

  it('respects an open start bound', () => {
    const openStart = {
      mode: 'custom' as const,
      endDate: '2026-09-30',
    }

    expect(
      isDateOutsideFilter(openStart, '2026-10-01'),
    ).toBe(true)
    expect(
      isDateOutsideFilter(openStart, '2020-01-01'),
    ).toBe(false)
  })

  it('never flags anything in Show All mode', () => {
    expect(
      isDateOutsideFilter({ mode: 'all' }, '1999-01-01'),
    ).toBe(false)
  })

  it('never flags anything in the default window mode', () => {
    // The default window is resolved server-side from the data after
    // the save, so the client has no basis to decide this locally.
    expect(
      isDateOutsideFilter(
        DEFAULT_TRANSACTION_FILTER,
        '1999-01-01',
      ),
    ).toBe(false)
  })

  it('ignores an absent date', () => {
    expect(isDateOutsideFilter(customRange, undefined)).toBe(
      false,
    )
  })

  it('ignores empty-string bounds', () => {
    expect(
      isDateOutsideFilter(
        { mode: 'custom', startDate: '', endDate: '' },
        '2026-09-15',
      ),
    ).toBe(false)
  })
})

describe('toSubmittedDate', () => {
  it('takes the date portion of a submitted timestamp', () => {
    expect(toSubmittedDate('2026-08-10T00:00:00')).toBe(
      '2026-08-10',
    )
  })

  it('passes a bare date through', () => {
    expect(toSubmittedDate('2026-08-10')).toBe('2026-08-10')
  })

  it('returns undefined when no date was submitted', () => {
    // A PATCH may legitimately omit transaction_date entirely.
    expect(toSubmittedDate(undefined)).toBeUndefined()
  })
})

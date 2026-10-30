import type { TransactionFilter } from './types'

// ISO YYYY-MM-DD strings compare correctly with < and >, so no Date
// objects are constructed here - the same reason the rest of this
// module keeps dates as strings end to end.

/**
 * Whether a transaction on `isoDate` falls outside the range the user
 * is currently filtering by - i.e. the row exists but will not appear
 * in the table.
 *
 * Only meaningful for a custom range. In 'all' mode nothing is out of
 * range, and in 'latest_available' mode the window is resolved
 * server-side from the data after the save, so the client cannot
 * decide this one locally without guessing.
 */
export function isDateOutsideFilter(
  filter: TransactionFilter,
  isoDate: string | undefined,
): boolean {
  if (filter.mode !== 'custom' || !isoDate) {
    return false
  }

  const beforeStart =
    filter.startDate !== undefined &&
    filter.startDate !== '' &&
    isoDate < filter.startDate

  const afterEnd =
    filter.endDate !== undefined &&
    filter.endDate !== '' &&
    isoDate > filter.endDate

  return beforeStart || afterEnd
}

/**
 * The date portion of a `transaction_date` as submitted to the API
 * ("2026-08-10T00:00:00" -> "2026-08-10"). Returns undefined when the
 * request carried no date at all, which a PATCH legitimately may.
 */
export function toSubmittedDate(
  transactionDate: string | undefined,
): string | undefined {
  return transactionDate?.split('T')[0]
}

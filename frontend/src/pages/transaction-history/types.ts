export interface Transaction {
  id: number

  // The immutable canonical link to the product (backend's update
  // contract has no product_id field at all - see
  // api/transactionTypes.ts). Needed both to pre-select/lock the
  // product in Edit mode and to invalidate the correct
  // ['forecast-timeseries', productId] query after update/delete.
  productId: number

  transactionNumber: string

  date: string

  furnitureProduct: string

  quantityProduced: number

  quantitySold: number

  // Needed to pre-fill the Edit form's Unit Price input - the table/
  // export never display this directly, only salesAmount (the real
  // backend-computed total_sales).
  unitPrice: number

  salesAmount: number

  productionCost: number

  profitEarned: number
}

// Which rule the view is asking the server to apply. Mirrors the
// backend's TransactionRangeMode (app/schemas/transaction.py).
export type TransactionRangeMode =
  | 'latest_available'
  | 'custom'
  | 'all'

// What the user has asked for. 'latest_available' sends no date
// params at all - the server resolves the window from the stored
// data (the 7 most recent distinct transaction dates), so the
// default view never depends on this browser's clock or timezone.
export interface TransactionFilter {
  mode: TransactionRangeMode

  // Only meaningful when mode is 'custom'. Either may be omitted for
  // a one-sided (open-ended) range. ISO YYYY-MM-DD, same string
  // convention as Transaction.date.
  startDate?: string
  endDate?: string
}

export const DEFAULT_TRANSACTION_FILTER: TransactionFilter = {
  mode: 'latest_available',
}

// The window the server actually applied - what is on screen. Either
// bound is null only for a one-sided custom range, or the whole
// object is null when no window was applied ('all') or none exists
// (empty table).
export interface TransactionDateRange {
  startDate: string | null
  endDate: string | null
  mode: TransactionRangeMode
}

// The full span of transaction dates that EXISTS, regardless of the
// active window. Drives the date inputs' min/max and the "nothing in
// this range" empty state. Never filter against this - that is what
// TransactionDateRange is for.
export interface TransactionAvailableRange {
  earliest: string
  latest: string
}

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
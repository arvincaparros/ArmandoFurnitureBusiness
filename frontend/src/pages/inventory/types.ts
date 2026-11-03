export interface ProductInventory {
  productId: number
  productName: string

  // Declared opening balance from the reviewed set; 0 when none was
  // declared for this product.
  openingQuantity: number

  // All-cycles totals.
  totalProduced: number
  totalSold: number

  // opening + totalProduced - totalSold. The real on-hand figure,
  // spanning every cycle - never reset by a new cycle.
  availableStock: number

  // CURRENT cycle only. These two reset when a new cycle starts;
  // availableStock does not.
  cycleProduced: number
  cycleSold: number
}

export interface InventoryOverview {
  cycleId: number | null
  cycleStartDate: string | null
  cycleEndDate: string | null
  stockValidationEnabled: boolean
  products: ProductInventory[]
}

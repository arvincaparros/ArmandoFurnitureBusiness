export interface Product {
  id: number
  productName: string
  sellingPrice: number
  isActive: boolean

  // Real ProductResourceRequirement quantities for this product,
  // keyed by resource id (the canonical relationship - never by
  // resource name). The Products table builds one column per
  // currently-active resource (see ProductTable.tsx) and looks this
  // map up by id; a resource with no entry here means this product
  // has no requirement for it, rendered as "-", never fabricated as
  // 0. Deactivating a resource removes its column entirely, so any
  // entry here for a since-deactivated resource simply stops being
  // displayed - not deleted, just no longer rendered.
  resourceQuantities: Record<number, number>

  // No backend field exists for any cost/profit figure on Product -
  // always null. These were already inert in the pre-integration
  // mock (hardcoded to 0 on save, never truly computed).
  materialCost: number | null
  laborCost: number | null
  machineCost: number | null
  totalCost: number | null
  profit: number | null
}

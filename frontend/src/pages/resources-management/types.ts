export interface Resource {
  id: number
  name: string
  resourceType: string
  unit: string
  isActive: boolean

  // Sourced from CycleResource on the latest production cycle, not
  // the global Resource record (which has no price/quantity fields -
  // see resourceAdapter.ts). null means no availability/price has
  // been configured for this resource in the current cycle yet -
  // never fabricated as 0.
  availableQuantity: number | null
  unitPrice: number | null
}

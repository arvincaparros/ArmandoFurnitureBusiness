import type {
  ResourceCreateRequest,
  ResourceUpdateRequest,
} from './api/resourceTypes'

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

export interface ResourcePricing {
  available_quantity: number
  unit_price: number
}

// Add mode, "Use Existing": the user picked an existing catalog
// resource, so the only write is availability/price for the latest
// production cycle (CycleResource, see useResources.ts) - never a
// new Resource row. The resource itself already exists in the
// database and keeps its id.
export interface ResourceInventorySubmission {
  kind: 'inventory'
  resourceId: number
  resourceName: string
  pricing: ResourcePricing
}

// Add mode, "Create New": the only branch that writes a new global
// Resource record (POST /api/resources). Pricing is the new row's
// availability/price for the latest production cycle, collected
// only when a cycle exists - null means the catalog row is created
// on its own and can be priced later.
export interface ResourceCreateSubmission {
  kind: 'create'
  resourceName: string
  data: ResourceCreateRequest
  pricing: ResourcePricing | null
}

// Edit mode: existing behavior - update the global catalog fields
// and, when a production cycle exists, availability/price.
export interface ResourceUpdateSubmission {
  kind: 'update'
  resourceId: number
  resourceName: string
  data: ResourceUpdateRequest
  pricing: ResourcePricing | null
}

export type ResourceSubmission =
  | ResourceInventorySubmission
  | ResourceCreateSubmission
  | ResourceUpdateSubmission

// Which slice of the resource catalog the page's table is showing.
// Inactive resources are soft-deleted rows that are kept (with their
// id and every historical reference) and can be reactivated.
export type ResourceStatusFilter = 'active' | 'inactive'

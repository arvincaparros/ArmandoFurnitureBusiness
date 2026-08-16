import type { ResourceResponse } from './resourceTypes'
import type { CycleResourceResponse } from './cycleResourceTypes'
import type { Resource } from '../types'

function parseDecimal(value: string | null | undefined): number {
  if (value === null || value === undefined) {
    return 0
  }

  const parsed = Number(value)

  return Number.isFinite(parsed) ? parsed : 0
}

// available_quantity/unit_price are CycleResource fields
// (production-cycle-scoped), not on the global Resource record - see
// cycleResourceApi.ts. Resolved here by resource id from the latest
// cycle's CycleResource rows; a resource with no entry means it
// hasn't been priced/stocked for the current cycle yet, rendered as
// null (never fabricated as 0).
export function toUiResource(
  resource: ResourceResponse,
  cycleResourcesByResourceId: Map<number, CycleResourceResponse> = new Map(),
): Resource {
  const cycleResource = cycleResourcesByResourceId.get(resource.id)

  return {
    id: resource.id,
    name: resource.name,
    resourceType: resource.resource_type,
    unit: resource.unit,
    isActive: resource.is_active,
    availableQuantity: cycleResource
      ? parseDecimal(cycleResource.available_quantity)
      : null,
    unitPrice: cycleResource
      ? parseDecimal(cycleResource.unit_price)
      : null,
  }
}

export function toUiResources(
  resources: ResourceResponse[],
  cycleResourcesByResourceId: Map<number, CycleResourceResponse> = new Map(),
): Resource[] {
  return resources.map((resource) =>
    toUiResource(resource, cycleResourcesByResourceId),
  )
}

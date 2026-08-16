import type {
  ProductResourceRequirementResponse,
  ResourceOption,
} from './productResourceTypes'

export interface ResolvedRequirement {
  id: number
  resourceId: number
  quantityRequired: number
  resourceName: string
  resourceUnit: string
  resourceIsActive: boolean
}

function parseDecimal(value: string): number {
  const parsed = Number(value)

  return Number.isFinite(parsed) ? parsed : 0
}

// Client-side join: ProductResourceRequirementResponse only has a
// bare resource_id (verified in backend/app/schemas/product.py - no
// name/type/unit on that endpoint), so display info comes from a
// separate GET /api/resources fetch, matched here by id.
export function resolveRequirements(
  requirements: ProductResourceRequirementResponse[],
  resources: ResourceOption[],
): ResolvedRequirement[] {
  const resourcesById = new Map(
    resources.map((resource) => [resource.id, resource]),
  )

  return requirements.map((requirement) => {
    const resource = resourcesById.get(requirement.resource_id)

    return {
      id: requirement.id,
      resourceId: requirement.resource_id,
      quantityRequired: parseDecimal(
        requirement.quantity_required,
      ),
      resourceName:
        resource?.name ??
        `Resource #${requirement.resource_id}`,
      resourceUnit: resource?.unit ?? '',
      resourceIsActive: resource?.is_active ?? false,
    }
  })
}

// Resources selectable for a NEW requirement: active only, and not
// already assigned to this product - the backend's unique
// constraint already rejects duplicates (verified: service-level
// pre-check + clean 400, not a raw IntegrityError), this is purely
// a UX convenience to avoid the user hitting that error at all.
export function getAvailableResourcesForNewRequirement(
  resources: ResourceOption[],
  existingRequirements: ProductResourceRequirementResponse[],
): ResourceOption[] {
  const assignedResourceIds = new Set(
    existingRequirements.map((requirement) => requirement.resource_id),
  )

  return resources.filter(
    (resource) =>
      resource.is_active &&
      !assignedResourceIds.has(resource.id),
  )
}

import type { ProductResponse } from './productTypes'
import type { ResolvedRequirement } from './productResourceAdapter'
import type { ResourceOption } from './productResourceTypes'
import type { CycleResourceResponse } from './cycleResourceTypes'
import type { Product } from '../types'

function parseDecimal(value: string | null | undefined): number {
  if (value === null || value === undefined) {
    return 0
  }

  const parsed = Number(value)

  return Number.isFinite(parsed) ? parsed : 0
}

type CostCategory = 'material' | 'labor' | 'machine'

interface ResourceCostRate {
  unitPrice: number
  category: CostCategory
}

// Mirrors backend/app/services/resource_utilization.py's
// _classify_resource_type() exactly - "labor"/"machine" are
// recognized specially, anything else (including "material") is
// treated as material. No dedicated backend cost-classification
// endpoint exists, so this reuses the same convention the backend
// already applies for utilization reporting rather than inventing a
// new one.
function classifyResourceType(resourceType: string): CostCategory {
  const normalized = resourceType.trim().toLowerCase()

  if (normalized === 'labor') return 'labor'
  if (normalized === 'machine') return 'machine'

  return 'material'
}

// Resource unit prices come from CycleResource on the latest
// production cycle (see cycleResourceApi.ts) - the only place a
// price exists in the backend. Only currently-active resources get a
// rate here, matching exactly which resources get a column in
// ProductTable.tsx, so a displayed cost is always traceable to
// visible cells x visible pricing.
export function buildResourceCostRates(
  activeResources: ResourceOption[],
  cycleResources: CycleResourceResponse[],
): Map<number, ResourceCostRate> {
  const unitPriceByResourceId = new Map(
    cycleResources.map((cycleResource) => [
      cycleResource.resource_id,
      parseDecimal(cycleResource.unit_price),
    ]),
  )

  const rates = new Map<number, ResourceCostRate>()

  for (const resource of activeResources) {
    const unitPrice = unitPriceByResourceId.get(resource.id)

    // No CycleResource entry yet for this resource in the current
    // cycle - leave it unset rather than fabricating a price, so any
    // product requiring it reports its cost as unknown (null) instead
    // of silently understating it.
    if (unitPrice === undefined) continue

    rates.set(resource.id, {
      unitPrice,
      category: classifyResourceType(resource.resource_type),
    })
  }

  return rates
}

interface CostBreakdown {
  materialCost: number | null
  laborCost: number | null
  machineCost: number | null
  totalCost: number | null
  profit: number | null
}

const UNPRICED_BREAKDOWN: CostBreakdown = {
  materialCost: null,
  laborCost: null,
  machineCost: null,
  totalCost: null,
  profit: null,
}

// Material Cost = sum(material resource qty x unit price), Labor
// Cost = labor usage x labor rate, Machine Cost = sum(machine
// resource qty x machine rate), Total Cost = the three summed,
// Profit = selling price - Total Cost - the exact formulas from the
// approved business model. If ANY active resource this product
// requires has no configured price, the whole breakdown stays null
// (never a partial/understated total).
function calculateCosts(
  resourceQuantities: Record<number, number>,
  activeResourceIds: number[],
  costRates: Map<number, ResourceCostRate>,
  sellingPrice: number,
): CostBreakdown {
  const requiredActiveResourceIds = activeResourceIds.filter(
    (id) => resourceQuantities[id] !== undefined,
  )

  const isFullyPriced = requiredActiveResourceIds.every((id) =>
    costRates.has(id),
  )

  if (!isFullyPriced) {
    return UNPRICED_BREAKDOWN
  }

  let materialCost = 0
  let laborCost = 0
  let machineCost = 0

  for (const id of requiredActiveResourceIds) {
    const rate = costRates.get(id)!
    const cost = resourceQuantities[id] * rate.unitPrice

    if (rate.category === 'labor') {
      laborCost += cost
    } else if (rate.category === 'machine') {
      machineCost += cost
    } else {
      materialCost += cost
    }
  }

  const totalCost = materialCost + laborCost + machineCost

  return {
    materialCost,
    laborCost,
    machineCost,
    totalCost,
    profit: sellingPrice - totalCost,
  }
}

// Resource id is the canonical relationship, never resource name -
// this is a plain re-keying of this product's already-resolved
// requirements (resolveRequirements() in productResourceAdapter.ts,
// the exact same function the Edit Product modal uses, not
// re-implemented here). A resource with no entry means this product
// has no requirement for it - never coerced to 0. Which resources
// actually get a column is decided entirely by ProductTable.tsx from
// the active resource catalog, not by this map's contents.
function resolveResourceQuantities(
  requirements: ResolvedRequirement[],
): Record<number, number> {
  const quantities: Record<number, number> = {}

  for (const requirement of requirements) {
    quantities[requirement.resourceId] =
      requirement.quantityRequired
  }

  return quantities
}

export function toUiProduct(
  product: ProductResponse,
  requirements: ResolvedRequirement[] = [],
  activeResourceIds: number[] = [],
  costRates: Map<number, ResourceCostRate> = new Map(),
): Product {
  const sellingPrice = parseDecimal(product.selling_price)
  const resourceQuantities = resolveResourceQuantities(requirements)

  const costs = calculateCosts(
    resourceQuantities,
    activeResourceIds,
    costRates,
    sellingPrice,
  )

  return {
    id: product.id,
    productName: product.name,
    sellingPrice,
    isActive: product.is_active,

    resourceQuantities,

    ...costs,
  }
}

export function toUiProducts(
  products: ProductResponse[],
  requirementsByProductId: Map<number, ResolvedRequirement[]> = new Map(),
  activeResourceIds: number[] = [],
  costRates: Map<number, ResourceCostRate> = new Map(),
): Product[] {
  return products.map((product) =>
    toUiProduct(
      product,
      requirementsByProductId.get(product.id) ?? [],
      activeResourceIds,
      costRates,
    ),
  )
}

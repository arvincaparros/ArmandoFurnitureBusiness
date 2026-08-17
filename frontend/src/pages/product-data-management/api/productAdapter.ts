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

type CostCategory = 'material' | 'machine'

interface ResourceCostRate {
  unitPrice: number
  category: CostCategory
}

// Mirrors backend/app/services/resource_utilization.py's
// _classify_resource_type() exactly for "machine" - anything else
// (including "material") is treated as material. "labor" is
// deliberately NOT one of these categories: labor cost comes straight
// from Product.labor_cost (see calculateCosts below), never from a
// CycleResource rate, matching backend/app/services/optimization.py::
// calculate_unit_profit exactly (the client's cost model proves labor
// cost varies per product independent of labor hours). Labor hours
// still get their own resource column via ProductTable.tsx's
// resourceQuantities - only the COST source changed.
function classifyResourceType(resourceType: string): CostCategory {
  const normalized = resourceType.trim().toLowerCase()

  if (normalized === 'machine') return 'machine'

  return 'material'
}

// Resource unit prices come from CycleResource on the latest
// production cycle (see cycleResourceApi.ts) - the only place a
// price exists in the backend. Only currently-active, non-labor
// resources get a rate here, matching exactly which resources get a
// column in ProductTable.tsx, so a displayed cost is always traceable
// to visible cells x visible pricing.
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
    if (resource.resource_type.trim().toLowerCase() === 'labor') {
      continue
    }

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

// Material Cost = sum(material resource qty x unit price), Machine
// Cost = sum(machine resource qty x machine rate), Labor Cost =
// Product.labor_cost directly (a per-product value, not a resource
// rate - see classifyResourceType above), Total Cost = the three
// summed, Profit = selling price - Total Cost - the exact formulas
// from backend/app/services/optimization.py::calculate_unit_profit.
// pricedResourceIds is the active catalog with labor already excluded
// by the caller (see toUiProduct) - if this product requires any
// OTHER active resource that has no configured CycleResource price,
// the whole breakdown stays null (never a partial/understated total).
// Labor is never part of that check: laborCost comes straight from
// the product record, so it's always known once the product itself
// has loaded.
function calculateCosts(
  resourceQuantities: Record<number, number>,
  pricedResourceIds: number[],
  costRates: Map<number, ResourceCostRate>,
  sellingPrice: number,
  laborCost: number,
): CostBreakdown {
  const requiredResourceIds = pricedResourceIds.filter(
    (id) => resourceQuantities[id] !== undefined,
  )

  const isFullyPriced = requiredResourceIds.every((id) =>
    costRates.has(id),
  )

  if (!isFullyPriced) {
    return UNPRICED_BREAKDOWN
  }

  let materialCost = 0
  let machineCost = 0

  for (const id of requiredResourceIds) {
    const rate = costRates.get(id)!
    const cost = resourceQuantities[id] * rate.unitPrice

    if (rate.category === 'machine') {
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
  activeResources: ResourceOption[] = [],
  costRates: Map<number, ResourceCostRate> = new Map(),
): Product {
  const sellingPrice = parseDecimal(product.selling_price)
  const laborCost = parseDecimal(product.labor_cost)
  const resourceQuantities = resolveResourceQuantities(requirements)

  // Labor is excluded here (not just from costRates) so
  // calculateCosts's "fully priced" check never waits on a labor
  // CycleResource price that no longer has anything to do with cost.
  const pricedResourceIds = activeResources
    .filter(
      (resource) =>
        resource.resource_type.trim().toLowerCase() !== 'labor',
    )
    .map((resource) => resource.id)

  const costs = calculateCosts(
    resourceQuantities,
    pricedResourceIds,
    costRates,
    sellingPrice,
    laborCost,
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
  activeResources: ResourceOption[] = [],
  costRates: Map<number, ResourceCostRate> = new Map(),
): Product[] {
  return products.map((product) =>
    toUiProduct(
      product,
      requirementsByProductId.get(product.id) ?? [],
      activeResources,
      costRates,
    ),
  )
}

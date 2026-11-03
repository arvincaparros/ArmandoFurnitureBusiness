import type {
  ResourceUtilizationItem,
  ResourceUtilizationResponse,
} from './utilizationTypes'

import type {
  Bottleneck,
  UtilizationResource,
  UtilizationSummary,
} from '../types'

import { resolveUtilizationStatus } from '../utilizationStatus'

// Every numeric field in ResourceUtilizationResponse is a Decimal
// serialized as a JSON string (confirmed live - e.g. "0E-8" for a
// zero remaining_quantity that round-tripped through a Numeric
// column, and total_labor_hours_used showing more decimal places
// than total_labor_hours_capacity since the former passes through a
// multiplication step). Number() correctly parses both forms; no
// further precision-sensitive math is performed on these values
// here, only display formatting.
function parseDecimal(value: string): number {
  const parsed = Number(value)

  return Number.isFinite(parsed) ? parsed : 0
}

// Display cap (approved business rule): the backend's
// utilization_rate/remaining_quantity are the TRUE, uncapped figures
// - consumption can genuinely exceed declared capacity now that
// repeated Apply is allowed (see optimization.py::apply_optimization),
// and that truth is exactly what's preserved in
// ProductionApplicationResourceItem and every historical snapshot.
// This report's cards/table/charts/progress bars must never show
// more than 100% utilized or less than zero remaining, though -
// clamped here, at the display boundary, rather than anywhere the
// true figures are computed or stored. totalConsumed below is
// deliberately NOT clamped: actual consumption is always shown as-is,
// only the derived utilization%/remaining are capped.
function clampUtilizationPercent(value: number): number {
  return Math.min(value, 100)
}

function clampRemainingQuantity(value: number): number {
  return Math.max(value, 0)
}

// Same cap, for the "Total Labor/Machine Hours Used" summary cards:
// displayed used = min(actual used, capacity). Capacity is passed
// through unchanged by the caller - never clamped itself.
function clampUsedHours(used: number, capacity: number): number {
  return Math.min(used, capacity)
}

// Single-item mapper reused for the main resources list, the at-risk
// list, and the most-constrained resource - all three are the exact
// same backend shape (ResourceUtilizationItem).
function toUiResource(
  resource: ResourceUtilizationItem,
): UtilizationResource {
  return {
    id: resource.resource_id,
    resourceName: resource.resource_name,
    unit: resource.unit,
    totalConsumed: parseDecimal(resource.consumed_quantity),
    totalRemaining: clampRemainingQuantity(
      parseDecimal(resource.remaining_quantity),
    ),
    // The backend computes this as consumed / available * 100 (not
    // renormalized or recalculated here) - clamped to 100 for
    // display per the approved capping rule.
    utilizationPercent: clampUtilizationPercent(
      parseDecimal(resource.utilization_rate),
    ),
    status: resolveUtilizationStatus(resource.status),
  }
}

// materialResourceCount/mostConstrained replace the old blended
// overall_utilization_rate/total_raw_materials_consumed fields here
// deliberately - those summed incompatible units (kg + hours + pcs)
// into one meaningless number. The backend still computes and
// returns them (kept for wire compatibility), this adapter simply no
// longer reads them.
export function toUiSummary(
  data: ResourceUtilizationResponse,
): UtilizationSummary {
  const laborCapacity = parseDecimal(
    data.total_labor_hours_capacity,
  )
  const machineCapacity = parseDecimal(
    data.total_machine_hours_capacity,
  )

  return {
    materialResourceCount: data.material_resource_count,
    mostConstrained: data.most_constrained_resource
      ? toUiResource(data.most_constrained_resource)
      : null,
    // Capped to the corresponding capacity for display (approved
    // business rule, same as totalRemaining/utilizationPercent
    // above): the backend figure is the TRUE, uncapped total across
    // every labor/machine resource - repeated Apply can genuinely
    // push it well past capacity now - but "Total Labor/Machine
    // Hours Used" must never show more used than the capacity shown
    // right next to it. Capacity itself is never clamped.
    laborUsed: clampUsedHours(
      parseDecimal(data.total_labor_hours_used),
      laborCapacity,
    ),
    laborCapacity,
    machineUsed: clampUsedHours(
      parseDecimal(data.total_machine_hours_used),
      machineCapacity,
    ),
    machineCapacity,
  }
}

export function toUiResources(
  data: ResourceUtilizationResponse,
): UtilizationResource[] {
  return data.resources.map(toUiResource)
}

// The proactive "at risk" tier (90-<100% utilization) - distinct from
// bottlenecks[] below, which is the pre-existing true-bottleneck list
// (remaining_quantity <= 0, unchanged). A resource is never in both.
export function toUiAtRiskResources(
  data: ResourceUtilizationResponse,
): UtilizationResource[] {
  return data.at_risk_resources.map(toUiResource)
}

// bottlenecks[] has no free-text "reason"/"recommendation" field -
// only structured is_binding/shortage_quantity/remaining_quantity
// (verified in backend/app/schemas/utilization.py). The mock's
// prose fields have no backend source; this presents the backend's
// own structured determination in a short readable sentence rather
// than fabricating advice.
export function toUiBottlenecks(
  data: ResourceUtilizationResponse,
): Bottleneck[] {
  return data.bottlenecks.map((bottleneck) => {
    const shortage = parseDecimal(bottleneck.shortage_quantity)

    const reason = bottleneck.is_binding
      ? `Fully utilized - 0 ${bottleneck.unit} remaining.`
      : `Over-allocated by ${shortage} ${bottleneck.unit}.`

    return {
      id: bottleneck.resource_id,
      resource: bottleneck.resource_name,
      unit: bottleneck.unit,
      remainingQuantity: parseDecimal(
        bottleneck.remaining_quantity,
      ),
      isBinding: bottleneck.is_binding,
      shortageQuantity: shortage,
      reason,
    }
  })
}

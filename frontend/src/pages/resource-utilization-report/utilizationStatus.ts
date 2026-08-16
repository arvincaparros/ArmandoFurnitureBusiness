// Mirrors backend/app/services/resource_utilization.py's
// classify_utilization_status() four-tier thresholds exactly
// (normal < 80, high 80-<90, at_risk 90-<100, bottleneck >= 100) -
// the backend computes and returns `status` directly, this is only
// the display metadata (label/color) for whichever status it sent.
// Shared across UtilizationTable, UtilizationBarChart, and
// BottleneckAlert in this module so all three agree on the same
// green/yellow/orange/red convention rather than each inventing its
// own thresholds (which is what UtilizationTable/UtilizationBarChart
// each did independently before this change).
export type UtilizationStatus =
  | 'normal'
  | 'high'
  | 'at_risk'
  | 'bottleneck'

interface UtilizationStatusMeta {
  label: string
  color: string
  hex: string
}

export const UTILIZATION_STATUS_META: Record<
  UtilizationStatus,
  UtilizationStatusMeta
> = {
  normal: { label: 'Normal', color: 'green', hex: '#16A34A' },
  high: { label: 'High', color: 'yellow', hex: '#D97706' },
  at_risk: { label: 'At Risk', color: 'orange', hex: '#EA580C' },
  bottleneck: { label: 'Bottleneck', color: 'red', hex: '#DC2626' },
}

// The backend's `status` field is a plain str (see
// backend/app/schemas/utilization.py's comment on why it isn't a
// stricter Literal) - this narrows it defensively so an unexpected
// value still renders sensibly instead of crashing the lookup.
export function resolveUtilizationStatus(
  status: string,
): UtilizationStatus {
  if (status in UTILIZATION_STATUS_META) {
    return status as UtilizationStatus
  }

  return 'normal'
}

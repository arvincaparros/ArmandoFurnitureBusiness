import type { WeekReferenceCompareResult } from '../api/weekReferenceTypes'

interface ResourceUtilizationTableProps {
  resourceUsage: WeekReferenceCompareResult['resource_usage']
  resourceNames: Record<string, string>
  resourceUnits: Record<string, string>
}

function formatWithUnit(value: string, unit: string | undefined): string {
  return unit ? `${value} ${unit}` : value
}

// Preserves the existing Available/Consumed/Remaining/Utilization%
// display, but Consumed here is derived from the ACTUAL generated
// quantities and the real BOM (see backend
// app/services/week_reference.py::_resource_usage) - never a stale
// snapshot, and never forced to 100% for every resource regardless
// of what was actually produced.
export function ResourceUtilizationTable({
  resourceUsage,
  resourceNames,
  resourceUnits,
}: ResourceUtilizationTableProps) {
  return (
    <table>
      <thead>
        <tr>
          <th>Resource</th>
          <th>Available</th>
          <th>Consumed</th>
          <th>Remaining</th>
          <th>Utilization %</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(resourceUsage).map(([key, row]) => (
          <tr key={key}>
            <td>{resourceNames[key] ?? key}</td>
            <td>{formatWithUnit(row.available, resourceUnits[key])}</td>
            <td>{formatWithUnit(row.consumed, resourceUnits[key])}</td>
            <td>{formatWithUnit(row.remaining, resourceUnits[key])}</td>
            <td>{row.utilization_rate}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

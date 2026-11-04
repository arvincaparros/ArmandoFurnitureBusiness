import type { WeekReferenceSummary } from '../api/weekReferenceTypes'

interface ReferenceResourceTableProps {
  week: WeekReferenceSummary
  overrides: Record<string, number>
  onOverrideChange: (resourceKey: string, value: number) => void
}

// Student/panel-editable resource table for the selected week.
// Deliberately NOT read-only/locked (requirement 2) - every input
// starts pre-filled with the week's historical reference value, but
// nothing here prevents changing it, and nothing here blocks
// Generate on a changed value either.
export function ReferenceResourceTable({
  week,
  overrides,
  onOverrideChange,
}: ReferenceResourceTableProps) {
  return (
    <table>
      <thead>
        <tr>
          <th>Resource</th>
          <th>Reference quantity</th>
          <th>Unit</th>
          <th>Your value</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(week.resources).map(([key, resource]) => (
          <tr key={key}>
            <td>{resource.name}</td>
            <td>{resource.available}</td>
            <td>{resource.unit}</td>
            <td>
              <input
                aria-label={`${resource.name} quantity`}
                type="number"
                step="0.0001"
                value={overrides[key] ?? Number(resource.available)}
                onChange={(event) =>
                  onOverrideChange(key, Number(event.target.value))
                }
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

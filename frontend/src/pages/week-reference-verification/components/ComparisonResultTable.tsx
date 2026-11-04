import type { WeekReferenceCompareResult } from '../api/weekReferenceTypes'

interface ComparisonResultTableProps {
  result: WeekReferenceCompareResult
  productNames: Record<string, string>
}

const STATUS_LABEL: Record<
  WeekReferenceCompareResult['reference_match_status'],
  string
> = {
  EXACT_MATCH: 'Exact Reference Match',
  MODIFIED_INPUT: 'Modified Inputs',
  REFERENCE_INPUT_MISMATCH: 'Reference resources, but result differs',
}

export function ComparisonResultTable({
  result,
  productNames,
}: ComparisonResultTableProps) {
  const productKeys = Object.keys(result.reference_allocation)

  return (
    <div>
      <p data-testid="reference-match-status">
        {STATUS_LABEL[result.reference_match_status]}
      </p>

      <table>
        <thead>
          <tr>
            <th>Product</th>
            <th>Expected quantity</th>
            <th>Generated quantity</th>
            <th>Difference</th>
          </tr>
        </thead>
        <tbody>
          {productKeys.map((key) => {
            const expected = result.reference_allocation[key] ?? 0
            const generated = result.computed_allocation[key] ?? 0
            const difference = result.allocation_difference[key] ?? 0

            return (
              <tr key={key}>
                <td>{productNames[key] ?? key}</td>
                <td>{expected}</td>
                <td>{generated}</td>
                <td>{difference > 0 ? `+${difference}` : difference}</td>
              </tr>
            )
          })}
          <tr>
            <td>Total</td>
            <td>{result.reference_total}</td>
            <td>{result.computed_total}</td>
            <td>{result.computed_total - result.reference_total}</td>
          </tr>
        </tbody>
      </table>

      <table>
        <tbody>
          <tr>
            <td>Expected profit</td>
            <td>{result.reference_profit}</td>
          </tr>
          <tr>
            <td>Generated profit</td>
            <td>{result.computed_profit}</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}

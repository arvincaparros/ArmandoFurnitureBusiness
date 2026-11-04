import { ComparisonResultTable } from './components/ComparisonResultTable'
import { ReferenceResourceTable } from './components/ReferenceResourceTable'
import { ResourceUtilizationTable } from './components/ResourceUtilizationTable'
import useWeekReferenceVerification from './hooks/useWeekReferenceVerification'

// Product names/units are derived from the currently-selected week's
// own reference payload rather than a second fetch - the backend
// already returns every product/resource name & unit on every week
// summary and compare response (requirement 5: preserve the
// workbook's own naming and units).
const PRODUCT_NAMES: Record<string, string> = {
  dining_table_4: 'Dining table (4 seater)',
  dining_table_6: 'Dining table (6 seater)',
  dining_table_8: 'Dining table (8 seater)',
  ordinary_table: 'Ordinary table',
  bed_frame: 'Bed frame',
  door_60: 'Door (60x210)',
  door_70: 'Door (70x210)',
  door_80: 'Door (80x210)',
  door_90: 'Door (90x210)',
  high_chair: 'High chair',
  ordinary_chair: 'Ordinary chair',
}

// The backend returns a plain-English `detail` string on the 400/404
// error responses this page can hit (unknown week, or the rare case
// the real solver itself raises - see WeekReferenceInfeasibleError) -
// surfaced here instead of axios's generic "Request failed with
// status code 400", so requirement 8's "clear error" is an actual
// clear error, not a status code.
function extractErrorMessage(error: unknown): string {
  const detail = (
    error as { response?: { data?: { detail?: string } } }
  ).response?.data?.detail

  if (detail) {
    return detail
  }

  return (error as Error).message ?? 'Unable to run the solver for this input.'
}

export default function WeekReferenceVerificationPage() {
  const {
    weeks,
    isLoadingWeeks,
    selectedWeek,
    selectWeek,
    currentWeek,
    resourceOverrides,
    setResourceOverride,
    runComparison,
    result,
    isComparing,
    compareError,
  } = useWeekReferenceVerification()

  const resourceNames = currentWeek
    ? Object.fromEntries(
        Object.entries(currentWeek.resources).map(([key, resource]) => [
          key,
          resource.name,
        ]),
      )
    : {}

  const resourceUnits = currentWeek
    ? Object.fromEntries(
        Object.entries(currentWeek.resources).map(([key, resource]) => [
          key,
          resource.unit,
        ]),
      )
    : {}

  return (
    <div>
      <h1>Week Reference Verification</h1>
      <p>
        Compare the actual ILP solver against the official weekly data
        reference workbook (Weeks 1-8).
      </p>

      {isLoadingWeeks && <p>Loading reference weeks...</p>}

      {!isLoadingWeeks && weeks.length > 0 && (
        <select
          value={selectedWeek}
          onChange={(event) => selectWeek(Number(event.target.value))}
        >
          {weeks.map((week) => (
            <option key={week.week} value={week.week}>
              Week {week.week}
              {!week.is_verified ? ' (unverified)' : ''}
            </option>
          ))}
        </select>
      )}

      {currentWeek && !currentWeek.is_verified && (
        <p role="alert">
          This week's historical configuration could not be verified -
          results shown are informational only.
        </p>
      )}

      {currentWeek && (
        <ReferenceResourceTable
          week={currentWeek}
          overrides={resourceOverrides}
          onOverrideChange={setResourceOverride}
        />
      )}

      <button
        type="button"
        onClick={() => void runComparison()}
        disabled={isComparing || !currentWeek}
      >
        {isComparing ? 'Running...' : 'Run against solver'}
      </button>

      {compareError && (
        <p role="alert">
          {extractErrorMessage(compareError)}
        </p>
      )}

      {result && (
        <>
          <ComparisonResultTable result={result} productNames={PRODUCT_NAMES} />
          <ResourceUtilizationTable
            resourceUsage={result.resource_usage}
            resourceNames={resourceNames}
            resourceUnits={resourceUnits}
          />
        </>
      )}
    </div>
  )
}

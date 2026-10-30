import { useState } from 'react'

import {
  Button,
  Group,
  Text,
  TextInput,
} from '@mantine/core'

import { List, RotateCcw } from 'lucide-react'

import {
  DEFAULT_TRANSACTION_FILTER,
  type TransactionAvailableRange,
  type TransactionFilter,
} from '../types'

interface TransactionDateRangeFilterProps {
  filter: TransactionFilter
  available: TransactionAvailableRange | null
  onChange: (filter: TransactionFilter) => void
}

// Native `type="date"` inputs, the same convention
// AddTransactionModal already uses - deliberately not @mantine/dates,
// which is not a dependency of this project and would be a new one
// just for two inputs.
//
// ISO YYYY-MM-DD strings throughout, never Date objects: these go
// straight to the API as query params and compare correctly as
// strings, so there is no point at which a timezone could shift the
// chosen day by one.
const TransactionDateRangeFilter = ({
  filter,
  available,
  onChange,
}: TransactionDateRangeFilterProps) => {
  const [startDraft, setStartDraft] = useState(
    filter.startDate ?? '',
  )

  const [endDraft, setEndDraft] = useState(
    filter.endDate ?? '',
  )

  // Resync when the filter is changed from outside this component -
  // "Show All" and "Most recent" both clear the applied dates, and
  // the inputs must follow rather than keep showing a range that is
  // no longer in effect.
  //
  // Adjusted during render against the previously seen prop rather
  // than in an effect: the effect version paints one frame with the
  // stale dates still in the inputs before correcting itself, and is
  // what react-hooks/set-state-in-effect flags. Typing in the inputs
  // does not change `filter`, so drafts are never clobbered mid-edit.
  const [syncedFilter, setSyncedFilter] = useState(filter)

  if (syncedFilter !== filter) {
    setSyncedFilter(filter)
    setStartDraft(filter.startDate ?? '')
    setEndDraft(filter.endDate ?? '')
  }

  // Lexicographic comparison is exact for YYYY-MM-DD.
  const isInvalidRange =
    startDraft !== '' &&
    endDraft !== '' &&
    endDraft < startDraft

  const hasDraft = startDraft !== '' || endDraft !== ''

  // The backend validates this too (and returns 400), but blocking
  // Apply means the invalid request is never sent in the first place.
  const canApply = hasDraft && !isInvalidRange

  const handleApply = () => {
    if (!canApply) {
      return
    }

    onChange({
      mode: 'custom',
      startDate: startDraft === '' ? undefined : startDraft,
      endDate: endDraft === '' ? undefined : endDraft,
    })
  }

  const handleShowAll = () => {
    onChange({ mode: 'all' })
  }

  const handleReset = () => {
    onChange(DEFAULT_TRANSACTION_FILTER)
  }

  return (
    <Group
      justify="space-between"
      align="flex-end"
      mb="md"
      wrap="wrap"
      gap="sm"
    >
      <Group align="flex-end" gap="sm" wrap="wrap">
        <TextInput
          radius="md"
          label="From"
          type="date"
          value={startDraft}
          onChange={(event) =>
            setStartDraft(event.currentTarget.value)
          }
          w={170}
        />

        <TextInput
          radius="md"
          label="To"
          type="date"
          value={endDraft}
          onChange={(event) =>
            setEndDraft(event.currentTarget.value)
          }
          error={
            isInvalidRange
              ? 'End date cannot be earlier than start date'
              : undefined
          }
          w={170}
        />

        <Button
          onClick={handleApply}
          disabled={!canApply}
        >
          Apply
        </Button>

        <Button
          variant="light"
          leftSection={<RotateCcw size={16} />}
          onClick={handleReset}
          disabled={filter.mode === 'latest_available'}
        >
          Most recent
        </Button>

        <Button
          variant="light"
          leftSection={<List size={16} />}
          onClick={handleShowAll}
          disabled={filter.mode === 'all'}
        >
          Show All
        </Button>
      </Group>

      {available !== null && (
        <Text size="xs" c="dimmed">
          Recorded transactions span {available.earliest} to{' '}
          {available.latest}
        </Text>
      )}
    </Group>
  )
}

export default TransactionDateRangeFilter

import {
  AlertTriangle,
  CheckCircle2,
  Minus,
} from 'lucide-react'

import {
  Box,
  ScrollArea,
  Tooltip,
} from '@mantine/core'

import AppTable, {
  type Column,
} from '../../../components/tables/AppTable'

import type { ForecastItem } from '../types'

interface ForecastTableProps {
  forecastItems: ForecastItem[]
  isLoading: boolean
  isError: boolean
}

// Approved mapping (Demand Forecasting Phase D): READY = success/green
// check, LOW_CONFIDENCE = warning/amber (forecast exists, confidence is
// limited - not a failure), NO_DATA = neutral/dash (insufficient
// qualifying history). Mirrors app/services/forecasting.py::
// determine_forecast_status exactly - no other status values exist.
const statusIndicator: Record<
  ForecastItem['status'],
  { icon: typeof CheckCircle2; color: string; label: string }
> = {
  READY: {
    icon: CheckCircle2,
    color: 'green',
    label: 'Ready',
  },
  LOW_CONFIDENCE: {
    icon: AlertTriangle,
    color: 'orange',
    label: 'Low confidence',
  },
  NO_DATA: {
    icon: Minus,
    color: 'gray',
    label: 'No data',
  },
}

const ForecastTable = ({
  forecastItems,
  isLoading,
  isError,
}: ForecastTableProps) => {
  const columns: Column<ForecastItem>[] = [
    {
      accessor: 'furnitureProduct',
      title: 'Furniture Product',
    },
    {
      accessor: 'historicalSales',
      title: 'Historical Sales (Units)',
    },
    {
      accessor: 'predictedDemand',
      title: 'Predicted Demand (Units)',
    },
    {
      accessor: 'forecastPeriod',
      title: 'Forecast Period',
    },
    {
      accessor: 'confidenceLevel',
      title: 'Confidence Level',
      render: (row) =>
        `${row.confidenceLevel.toFixed(1)}%`,
    },
    {
      accessor: 'status',
      title: 'Forecast Status',
      textAlign: 'center',
      render: (row) => {
        const indicator = statusIndicator[row.status]
        const Icon = indicator.icon

        return (
          <Tooltip label={indicator.label}>
            <Icon
              size={18}
              color={
                indicator.color === 'gray'
                  ? '#9ca3af'
                  : indicator.color === 'orange'
                    ? '#d97706'
                    : '#16a34a'
              }
              strokeWidth={2.5}
            />
          </Tooltip>
        )
      },
    },
  ]

  const emptyMessage = isLoading
    ? 'Loading forecast...'
    : isError
      ? 'Unable to load forecast.'
      : 'No forecast data available.'

  return (
    <Box
      style={{
        width: '100%',
        minWidth: 0,
      }}
    >
      <ScrollArea
        type="always"
        scrollbars="x"
        scrollbarSize={8}
        offsetScrollbars
        style={{
          width: '100%',
        }}
      >
        <Box
          style={{
            width: '100%',
            minWidth: 900,
          }}
        >
          <AppTable
            columns={columns}
            data={isLoading ? [] : forecastItems}
            emptyMessage={emptyMessage}
          />
        </Box>
      </ScrollArea>
    </Box>
  )
}

export default ForecastTable

import {
  Box,
  ScrollArea,
} from '@mantine/core'

import AppTable, {
  type Column,
} from '../../../components/tables/AppTable'

import type { ForecastTableItem } from '../types'

interface ForecastTableProps {
  forecastItems: ForecastTableItem[]
  isLoading: boolean
  isError: boolean
}

const ForecastTable = ({
  forecastItems,
  isLoading,
  isError,
}: ForecastTableProps) => {
  const columns: Column<ForecastTableItem>[] = [
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

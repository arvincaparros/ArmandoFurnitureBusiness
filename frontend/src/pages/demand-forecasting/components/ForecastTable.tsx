import {
  Box,
  ScrollArea,
} from '@mantine/core'

import AppTable, {
  type Column,
} from '../../../components/tables/AppTable'

import type { ForecastWeekRow } from '../types'

interface ForecastTableProps {
  weekRows: ForecastWeekRow[]
  isLoading: boolean
  isError: boolean
}

const ForecastTable = ({
  weekRows,
  isLoading,
  isError,
}: ForecastTableProps) => {
  const columns: Column<ForecastWeekRow>[] = [
    {
      accessor: 'furnitureProduct',
      title: 'Furniture Product',
    },
    {
      accessor: 'historicalSales',
      title: 'Historical Sales (Units)',
      render: (row) =>
        row.historicalSales === undefined ? '—' : row.historicalSales,
    },
    {
      accessor: 'predictedDemand',
      title: 'Predicted Demand (Units)',
      render: (row) =>
        row.predictedDemand === undefined ? '—' : row.predictedDemand,
    },
    {
      accessor: 'weekLabel',
      title: 'Forecast Period',
    },
    {
      accessor: 'confidenceLevel',
      title: 'Confidence Level',
      render: (row) =>
        row.confidenceLevel === undefined
          ? '—'
          : `${row.confidenceLevel.toFixed(1)}%`,
    },
  ]

  const emptyMessage = isLoading
    ? 'Loading forecast...'
    : isError
      ? 'Unable to load forecast.'
      : 'No forecast data available for this product.'

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
            data={isLoading ? [] : weekRows}
            emptyMessage={emptyMessage}
          />
        </Box>
      </ScrollArea>
    </Box>
  )
}

export default ForecastTable

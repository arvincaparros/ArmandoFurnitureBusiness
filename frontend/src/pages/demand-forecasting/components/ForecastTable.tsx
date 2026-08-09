import { CheckCircle2 } from 'lucide-react'

import {
  Box,
  ScrollArea,
} from '@mantine/core'

import AppTable, {
  type Column,
} from '../../../components/tables/AppTable'

import type { ForecastItem } from '../types'

interface ForecastTableProps {
  forecastItems: ForecastItem[]
}

const ForecastTable = ({
  forecastItems,
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
      render: (row) =>
        row.status === 'success' ? (
          <CheckCircle2
            size={18}
            color="green"
            strokeWidth={2.5}
          />
        ) : (
          row.status
        ),
    },
  ]

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
            width: 'max-content',
            minWidth: 900,
          }}
        >
          <AppTable
            columns={columns}
            data={forecastItems}
          />
        </Box>
      </ScrollArea>
    </Box>
  )
}

export default ForecastTable
import { Center, Loader, Text } from '@mantine/core'
import { LineChart } from '@mantine/charts'

import type { ForecastChartData } from '../types'

interface ForecastChartProps {
  data: ForecastChartData[]
  isLoading: boolean
  isError: boolean
  hasProducts: boolean
}

const ForecastChart = ({
  data,
  isLoading,
  isError,
  hasProducts,
}: ForecastChartProps) => {
  if (isLoading) {
    return (
      <Center h={280}>
        <Loader />
      </Center>
    )
  }

  if (isError) {
    return (
      <Center h={280}>
        <Text c="dimmed">
          Unable to load forecast timeseries.
        </Text>
      </Center>
    )
  }

  if (!hasProducts) {
    return (
      <Center h={280}>
        <Text c="dimmed">
          No products available.
        </Text>
      </Center>
    )
  }

  if (data.length === 0) {
    return (
      <Center h={280}>
        <Text c="dimmed">
          No forecast timeseries available for this product.
        </Text>
      </Center>
    )
  }

  // A product with no recorded sales still gets exactly one forecast
  // point (a flat 0-unit projection) from GET /api/forecast/timeseries,
  // which otherwise renders as an empty-looking chart. There is no
  // historical demand to plot until sales transactions exist, so say
  // that explicitly rather than drawing a lone zero dot.
  const hasHistoricalPoints = data.some(
    (point) => point.historicalDemand !== undefined,
  )

  if (!hasHistoricalPoints) {
    return (
      <Center h={280}>
        <Text c="dimmed" ta="center">
          No sales history for this product yet. Record sales
          transactions and run the demand forecast to see historical
          and forecasted demand.
        </Text>
      </Center>
    )
  }

  return (
    <LineChart
      h={280}
      data={data}
      dataKey="month"
      series={[
        {
          name: 'historicalDemand',
          label: 'Historical Demand',
        },
        {
          name: 'forecastedDemand',
          label: 'Forecasted Demand',
          strokeDasharray: '6 6',
        },
      ]}
      curveType="linear"
      withLegend
      withTooltip
      withDots
      valueFormatter={(value) =>
        `${value} units`
      }
    />
  )
}

export default ForecastChart

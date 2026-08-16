import { Center, Loader, Text } from '@mantine/core'
import { LineChart } from '@mantine/charts'

import type { ProfitTrend } from '../types'

interface OptimizationHistoryChartProps {
  data: ProfitTrend[]
  isLoading: boolean
  isError: boolean
}

const OptimizationHistoryChart = ({
  data,
  isLoading,
  isError,
}: OptimizationHistoryChartProps) => {
  if (isLoading) {
    return (
      <Center h={320}>
        <Loader />
      </Center>
    )
  }

  if (isError) {
    return (
      <Center h={320}>
        <Text c="dimmed">
          Unable to load optimization history.
        </Text>
      </Center>
    )
  }

  if (data.length === 0) {
    return (
      <Center h={320}>
        <Text c="dimmed">
          No optimization history found.
        </Text>
      </Center>
    )
  }

  return (
    <LineChart
      h={320}
      data={data}
      dataKey="optimizationId"
      series={[
        {
          name: 'profit',
          label: 'Profit',
        },
      ]}
      curveType="linear"
      withLegend
      withTooltip
      valueFormatter={(value) =>
        `₱${value.toLocaleString()}`
      }
      yAxisProps={{
        tickFormatter: (value) =>
          `₱${value.toLocaleString()}`,
      }}
    />
  )
}

export default OptimizationHistoryChart

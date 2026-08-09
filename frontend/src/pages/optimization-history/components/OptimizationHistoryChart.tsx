import { LineChart } from '@mantine/charts'

import type { ProfitTrend } from '../types'

interface OptimizationHistoryChartProps {
  data: ProfitTrend[]
}

const OptimizationHistoryChart = ({
  data,
}: OptimizationHistoryChartProps) => {
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
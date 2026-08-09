import { LineChart } from '@mantine/charts'

import type { ForecastChartData } from '../types'

interface ForecastChartProps {
  data: ForecastChartData[]
}

const ForecastChart = ({
  data,
}: ForecastChartProps) => {
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
      yAxisProps={{
        domain: [0, 360],
      }}
      valueFormatter={(value) =>
        `${value} units`
      }
    />
  )
}

export default ForecastChart
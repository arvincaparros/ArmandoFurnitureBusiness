import { Grid } from '@mantine/core'

import ChartCard from '../../../components/cards/ChartCard'

import {
  LineChart,
  PieChart,
} from '../../../components/charts'

import {
  productionTrend,
  resourceUsage,
} from '../mock/dashboardData'

const DashboardCharts = () => {
  return (
    <Grid>
      <Grid.Col span={{ base: 12, lg: 8 }}>
        <ChartCard
          title="Production Trend"
          subtitle="Last 6 months"
        >
          <LineChart
            data={productionTrend}
            xKey="month"
            yKey="production"
          />
        </ChartCard>
      </Grid.Col>

      <Grid.Col span={{ base: 12, lg: 4 }}>
        <ChartCard title="Resource Usage">
          <PieChart
            data={resourceUsage}
            nameKey="name"
            valueKey="value"
          />
        </ChartCard>
      </Grid.Col>
    </Grid>
  )
}

export default DashboardCharts
import { Grid } from '@mantine/core'

import StatCard from '../../../components/cards/StatCard'

import { dashboardStats } from '../mock/dashboardData'

const DashboardStats = () => {
  return (
    <Grid mb="sm">
      {dashboardStats.map((stat) => (
        <Grid.Col
          key={stat.id}
          span={{ base: 12, md: 6, lg: 3 }}
        >
          <StatCard
            title={stat.title}
            value={stat.value}
            icon={stat.icon}
            description={stat.description}
            color={stat.color}
          />
        </Grid.Col>
      ))}
    </Grid>
  )
}

export default DashboardStats

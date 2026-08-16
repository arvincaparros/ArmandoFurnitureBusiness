import { Grid, Box, Stack } from '@mantine/core'

import PageHeader from '../../components/common/PageHeader'

import DashboardStats from './components/DashboardStats'
import DashboardRecommendations from './components/DashboardRecommendations'
import DashboardResourceUtilization from './components/DashboardResourceUtilization'
import DashboardQuickActions from './components/DashboardQuickActions'

import useDashboard from './hooks/useDashboard'

const DashboardPage = () => {
  const {
    stats,
    isStatsLoading,
    isStatsError,

    recommendations,
    isRecommendationsLoading,
    isRecommendationsError,

    resourceUtilization,
    isResourceUtilizationLoading,
    isResourceUtilizationError,
  } = useDashboard()

  return (
    <Stack gap="xs">
      <PageHeader
        title="Dashboard"
        subtitle="Overview of production capacity and projections."
      />

      <DashboardStats
        stats={stats}
        isLoading={isStatsLoading}
        isError={isStatsError}
      />

       <Box mb="sm">
        <DashboardQuickActions />
      </Box>

      <Grid>
        <Grid.Col span={{ base: 12, lg: 7 }}>
            <DashboardRecommendations
              recommendations={recommendations}
              isLoading={isRecommendationsLoading}
              isError={isRecommendationsError}
            />
        </Grid.Col>

        <Grid.Col span={{ base: 12, lg: 5 }}>
            <DashboardResourceUtilization
              data={resourceUtilization}
              isLoading={isResourceUtilizationLoading}
              isError={isResourceUtilizationError}
            />
        </Grid.Col>
        </Grid>


    </Stack>
  )
}

export default DashboardPage
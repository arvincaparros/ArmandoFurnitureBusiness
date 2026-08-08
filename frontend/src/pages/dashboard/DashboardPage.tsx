import { Grid, Box, Stack } from '@mantine/core'

import PageHeader from '../../components/common/PageHeader'

import DashboardStats from './components/DashboardStats'
import DashboardRecommendations from './components/DashboardRecommendations'
import DashboardResourceUtilization from './components/DashboardResourceUtilization'
import DashboardQuickActions from './components/DashboardQuickActions'

const DashboardPage = () => {
  return (
    <Stack gap="xs">
      <PageHeader
        title="Dashboard"
        subtitle="Overview of production capacity and projections."
      />

      <DashboardStats />

       <Box mb="sm">
        <DashboardQuickActions />
      </Box>
   
      <Grid>
        <Grid.Col span={{ base: 12, lg: 7 }}>
            <DashboardRecommendations />
        </Grid.Col>

        <Grid.Col span={{ base: 12, lg: 5 }}>
            <DashboardResourceUtilization />
        </Grid.Col>
        </Grid>

     
    </Stack>
  )
}

export default DashboardPage
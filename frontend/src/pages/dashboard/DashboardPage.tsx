import { Flex, Box, Stack } from '@mantine/core'

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
        subtitle="Overview of production optimization and business performance."
      />

      <DashboardStats />
   
      <Flex gap="md" align="stretch">
        <Box flex={7}>
            <DashboardRecommendations />
        </Box>

        <Box flex={5}>
            <DashboardResourceUtilization />
        </Box>
      </Flex>

      <Box mt="sm">
        <DashboardQuickActions />
      </Box>
    </Stack>
  )
}

export default DashboardPage
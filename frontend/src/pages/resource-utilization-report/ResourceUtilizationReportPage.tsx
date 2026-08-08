import {
  Box,
  Grid,
  Stack,
} from '@mantine/core'

import PageHeader from '../../components/common/PageHeader'
import ChartCard from '../../components/cards/ChartCard'

import SummaryCards from './components/SummaryCards'
import UtilizationTable from './components/UtilizationTable'
import UtilizationPieChart from './components/UtilizationPieChart'
import BottleneckAlert from './components/BottleneckAlert'

import useResourceUtilization from './hooks/useResourceUtilization'
import { pieChartData } from './mock/utilizationData'

const ResourceUtilizationReportPage =
  () => {
    const {
      summary,
      resources,
      bottlenecks,
    } = useResourceUtilization()

    return (
      <>
        <PageHeader
          title="Resource Utilization Report"
          subtitle="Resource consumption and constraint analysis for optimization run."
        />

        <SummaryCards
          summary={summary}
        />

        <Grid mt="md">
          <Grid.Col
            span={{ base: 12, lg: 8 }}
          >
            <ChartCard
              title="Resource Utilization Summary"
              subtitle={`${resources.length} resources`}
            >
              <Box h="100%">
                <UtilizationTable
                  resources={resources}
                />
              </Box>
              
            </ChartCard>
          </Grid.Col>

          <Grid.Col
            span={{ base: 12, lg: 4 }}
          >
            <Stack>
              <UtilizationPieChart
                data={pieChartData}
              />

              <BottleneckAlert
                bottlenecks={
                  bottlenecks
                }
              />
            </Stack>
          </Grid.Col>
        </Grid>
      </>
    )
  }

export default ResourceUtilizationReportPage
import {
  Alert,
  Box,
  Grid,
  Group,
  Stack,
  Text,
} from '@mantine/core'

import { AlertCircle, Info } from 'lucide-react'

import PageHeader from '../../components/common/PageHeader'
import ChartCard from '../../components/cards/ChartCard'

import SummaryCards from './components/SummaryCards'
import UtilizationTable from './components/UtilizationTable'
import UtilizationBarChart from './components/UtilizationBarChart'
import BottleneckAlert from './components/BottleneckAlert'

import useResourceUtilization from './hooks/useResourceUtilization'

const ResourceUtilizationReportPage = () => {
  const {
    hasCycle,
    hasAppliedAllocation,
    summary,
    resources,
    bottlenecks,
    atRiskResources,
    isLoading,
    isError,
  } = useResourceUtilization()

  return (
    <>
      <PageHeader
        title="Resource Utilization Report"
        subtitle="Resource consumption and constraint analysis for optimization run."
      />

      {!hasCycle && !isLoading && (
        <Alert
          color="orange"
          icon={<AlertCircle size={18} />}
          mb="md"
        >
          No production cycle exists yet.
        </Alert>
      )}

      {hasCycle && !hasAppliedAllocation && !isLoading && (
        <Alert
          color="orange"
          icon={<AlertCircle size={18} />}
          mb="md"
        >
          No production allocation has been applied for this
          cycle. Generating a plan alone does not update this
          page - apply it from Production Allocation first.
        </Alert>
      )}

      {hasCycle && !isLoading && (
        <Group gap={6} mb="md" c="dimmed">
          <Info size={14} />

          <Text size="xs">
            Based on applied production for the current cycle -
            not the optimizer's preview.
          </Text>
        </Group>
      )}

      <SummaryCards
        summary={summary}
        isLoading={isLoading}
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
                isLoading={isLoading}
                isError={isError}
              />
            </Box>
          </ChartCard>
        </Grid.Col>

        <Grid.Col
          span={{ base: 12, lg: 4 }}
        >
          <Stack>
            <UtilizationBarChart
              resources={resources}
              isLoading={isLoading}
              isError={isError}
            />

            <BottleneckAlert
              bottlenecks={bottlenecks}
              atRiskResources={atRiskResources}
              resources={resources}
              isLoading={isLoading}
              isError={isError}
            />
          </Stack>
        </Grid.Col>
      </Grid>
    </>
  )
}

export default ResourceUtilizationReportPage

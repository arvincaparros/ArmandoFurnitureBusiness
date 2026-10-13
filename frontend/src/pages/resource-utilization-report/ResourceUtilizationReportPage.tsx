import {
  Alert,
  Box,
  Button,
  Grid,
  Group,
  Stack,
  Text,
} from '@mantine/core'

import { AlertCircle, Info } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import PageHeader from '../../components/common/PageHeader'
import ChartCard from '../../components/cards/ChartCard'

import SummaryCards from './components/SummaryCards'
import UtilizationTable from './components/UtilizationTable'
import UtilizationBarChart from './components/UtilizationBarChart'
import BottleneckAlert from './components/BottleneckAlert'

import useResourceUtilization from './hooks/useResourceUtilization'

// applied_at is always UTC (ProductionAllocation.applied_at uses
// datetime.utcnow) but arrives with no "Z"/offset suffix - same
// naive-UTC convention as resource-utilization-history's
// toDisplayDate, duplicated locally here rather than imported
// (per-module convention, see e.g. productionAllocationApi.ts).
// Returns null as-is so callers can omit the "(applied ...)" clause
// entirely for a null appliedAt instead of showing "Invalid Date".
function formatAppliedAt(appliedAt: string | null): string | null {
  if (appliedAt === null) {
    return null
  }

  const hasTimezone = /(Z|[+-]\d{2}:?\d{2})$/.test(appliedAt)
  const date = new Date(hasTimezone ? appliedAt : `${appliedAt}Z`)

  if (Number.isNaN(date.getTime())) {
    return null
  }

  return date.toLocaleString()
}

const ResourceUtilizationReportPage = () => {
  const navigate = useNavigate()

  const {
    hasCycle,
    hasAppliedAllocation,
    summary,
    resources,
    bottlenecks,
    atRiskResources,
    isLoading,
    isError,
    needsReoptimization,
    isAllocationInfeasible,
    appliedAt,
    feasibilityBottlenecks,
    isFeasibilityLoading,
    isFeasibilityError,
  } = useResourceUtilization()

  const displayAppliedAt = formatAppliedAt(appliedAt)

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

      {hasCycle
        && hasAppliedAllocation
        && !isFeasibilityLoading
        && isFeasibilityError && (
        <Alert
          color="gray"
          icon={<AlertCircle size={18} />}
          mb="md"
        >
          Unable to confirm whether this allocation needs
          re-optimization right now. The utilization numbers below
          are still from your last applied production allocation.
        </Alert>
      )}

      {hasCycle
        && hasAppliedAllocation
        && !isFeasibilityLoading
        && !isFeasibilityError
        && needsReoptimization && (
        <Alert
          color={isAllocationInfeasible ? 'red' : 'orange'}
          icon={<AlertCircle size={18} />}
          mb="md"
          title={
            isAllocationInfeasible
              ? 'Needs Review — Resource Shortage'
              : 'Needs Re-optimization'
          }
        >
          <Text size="sm">
            This report reflects your last applied production
            allocation{displayAppliedAt
              ? ` (applied ${displayAppliedAt})`
              : ''}, not a newly generated optimization preview.
            {' '}
            {isAllocationInfeasible
              ? 'Resources have changed since it was applied and it no longer fits within capacity.'
              : 'Resources have changed since it was applied - it may no longer be optimal.'}
            {' '}
            Generate and apply a new Production Plan to update
            these numbers.
          </Text>

          {feasibilityBottlenecks.length > 0 && (
            <Text size="sm" mt="xs">
              Shortage:{' '}
              {feasibilityBottlenecks
                .map(
                  (b) =>
                    `${b.resourceName} is short by ${b.shortageQuantity} ${b.unit}`,
                )
                .join('; ')}
              .
            </Text>
          )}

          <Button
            mt="sm"
            size="xs"
            variant="light"
            color={isAllocationInfeasible ? 'red' : 'orange'}
            onClick={() => navigate('/production')}
          >
            Go to Production Allocation
          </Button>
        </Alert>
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

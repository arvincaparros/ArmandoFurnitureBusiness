import { useState } from 'react'

import PageHeader from '../../components/common/PageHeader'
import ChartCard from '../../components/cards/ChartCard'

import {
  Alert,
  Box,
  Button,
  Grid,
  Group,
  Stack,
  Text,
  Tooltip,
} from '@mantine/core'

import { AlertCircle, CheckCircle2 } from 'lucide-react'

import GeneratePlanButton from './components/GeneratePlanButton'
import ProductionPlanTable from './components/ProductionPlanTable'
import SummaryCards from './components/SummaryCards'
import OptimizationInfoCard from './components/OptimizationInfoCard'
import ApplyConfirmModal from './components/ApplyConfirmModal'

import { getApiErrorMessage } from '../../api/apiError'
import { notify } from '../../utils/notify'

import useProductionAllocation from './hooks/useProductionAllocation'

const ProductionAllocationPage = () => {
  const {
    plans,
    summary,
    hasCycle,
    isLoading,
    isError,
    generatePlan,
    isGenerating,
    generateError,

    currentAllocation,
    isAllocationLoading,
    isAllocationError,

    canApply,
    applyToProduction,
    isApplying,
    applyError,

    needsReoptimization,
    isAllocationInfeasible,
    bottlenecks,
  } = useProductionAllocation()

  const [applyModalOpened, setApplyModalOpened] = useState(false)

  // Adaptive minimum demand (v2 plan): a nonzero shortfall on a
  // freshly-generated preview row means the optimizer had to deviate
  // from the original minimum vector - surfaced once here rather than
  // relying on the reader to notice individual "Unmet Demand" cells.
  // Scoped to `plans` (the preview) only, not `currentAllocation` (the
  // applied plan) - that table renders its own Unmet Demand cells
  // regardless, so an already-applied adaptive plan is never hidden,
  // just not re-announced here on a later page visit.
  const hasAdaptiveShortfall = plans.some(
    (plan) => (plan.shortfall ?? 0) > 0,
  )

  const handleConfirmApply = async () => {
    await applyToProduction()
    notify.applied()
  }

  const applyDisabled = !canApply || isGenerating || isApplying

  return (
    <>
      <PageHeader
        title="Production Allocation"
        subtitle="Optimize production quantities to maximize profit."
      />

      <Group>
        <GeneratePlanButton
          onGenerate={() => {
            void generatePlan()
          }}
          loading={isGenerating}
          disabled={!hasCycle || isGenerating}
        />

        {applyDisabled ? (
          <Tooltip
            label={
              canApply
                ? 'Please wait for the current operation to finish.'
                : 'Generate an optimal plan first.'
            }
          >
            <span>
              <Button
                variant="light"
                color="teal"
                leftSection={<CheckCircle2 size={18} />}
                disabled
              >
                Apply to Production
              </Button>
            </span>
          </Tooltip>
        ) : (
          <Button
            variant="light"
            color="teal"
            leftSection={<CheckCircle2 size={18} />}
            onClick={() => setApplyModalOpened(true)}
          >
            Apply to Production
          </Button>
        )}
      </Group>

      {generateError && (
        <Alert
          color="red"
          icon={<AlertCircle size={18} />}
          mt="md"
        >
          {getApiErrorMessage(
            generateError,
            'Unable to generate a production plan. Please try again.',
          )}
        </Alert>
      )}

      {hasAdaptiveShortfall && (
        <Alert
          color="orange"
          icon={<AlertCircle size={18} />}
          mt="md"
          title="Adaptive optimization applied"
        >
          Resources this cycle could not fully satisfy every product's
          minimum demand, so production targets were automatically
          adjusted to stay within capacity while covering as many
          furniture types as possible. See "Unmet Demand" below for
          which products are affected - original minimum demand values
          are unchanged.
        </Alert>
      )}

      {applyError && (
        <Alert
          color="red"
          icon={<AlertCircle size={18} />}
          mt="md"
        >
          {getApiErrorMessage(
            applyError,
            'Unable to apply the production plan. Please try again.',
          )}
        </Alert>
      )}

      <Grid
        mt="md"
        align="stretch"
      >
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <ChartCard
            title="Production Plan"
            subtitle={`${plans.length} furniture item${
              plans.length !== 1 ? 's' : ''
            }`}
          >
            <Box h="100%">
              <ProductionPlanTable
                plans={plans}
                isLoading={isLoading}
                isError={isError}
              />
            </Box>
          </ChartCard>
        </Grid.Col>

        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Stack h="100%">
            <SummaryCards summary={summary} />
            <OptimizationInfoCard summary={summary} />
          </Stack>
        </Grid.Col>
      </Grid>

      {needsReoptimization && currentAllocation.length > 0 && (
        <Alert
          color={isAllocationInfeasible ? 'red' : 'orange'}
          icon={<AlertCircle size={18} />}
          mt="md"
          title={
            isAllocationInfeasible
              ? 'Needs Review — Resource Shortage'
              : 'Needs Re-optimization'
          }
        >
          <Text size="sm">
            Your existing production allocation needs
            re-optimization: it may no longer be feasible or optimal
            based on the updated resources. Please generate a new
            Optimal Production Plan and apply it to update your
            production allocation.
          </Text>

          {bottlenecks.length > 0 && (
            <Text size="sm" mt="xs">
              Shortage:{' '}
              {bottlenecks
                .map(
                  (b) =>
                    `${b.resourceName} is short by ${b.shortageQuantity} ${b.unit}`,
                )
                .join('; ')}
              .
            </Text>
          )}
        </Alert>
      )}

      <Grid mt="md">
        <Grid.Col span={12}>
          <ChartCard
            title="Current Production Allocation"
            subtitle="The plan actually committed for this cycle - separate from the preview above until applied."
          >
            <Box h="100%">
              <Text size="xs" c="dimmed" mb="sm">
                Financial values are based on current product and
                resource prices and may differ from values at the
                time this allocation was applied.
              </Text>

              <ProductionPlanTable
                plans={currentAllocation}
                isLoading={isAllocationLoading}
                isError={isAllocationError}
                emptyMessage="No allocation has been committed for this cycle yet."
                showFinancialSummary
              />
            </Box>
          </ChartCard>
        </Grid.Col>
      </Grid>

      <ApplyConfirmModal
        opened={applyModalOpened}
        onClose={() => setApplyModalOpened(false)}
        onConfirm={handleConfirmApply}
      />
    </>
  )
}

export default ProductionAllocationPage

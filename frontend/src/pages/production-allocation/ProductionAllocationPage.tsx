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
  } = useProductionAllocation()

  const [applyModalOpened, setApplyModalOpened] = useState(false)

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

      <Grid mt="md">
        <Grid.Col span={12}>
          <ChartCard
            title="Current Production Allocation"
            subtitle="The plan actually committed for this cycle - separate from the preview above until applied."
          >
            <Box h="100%">
              <ProductionPlanTable
                plans={currentAllocation}
                isLoading={isAllocationLoading}
                isError={isAllocationError}
                emptyMessage="No allocation has been committed for this cycle yet."
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

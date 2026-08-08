import PageHeader from '../../components/common/PageHeader'
import ChartCard from '../../components/cards/ChartCard'

import {
  Box,
  Grid,
  Stack,
} from '@mantine/core'

import GeneratePlanButton from './components/GeneratePlanButton'
import ProductionPlanTable from './components/ProductionPlanTable'
import SummaryCards from './components/SummaryCards'
import OptimizationInfoCard from './components/OptimizationInfoCard'

import useProductionAllocation from './hooks/useProductionAllocation'

const ProductionAllocationPage = () => {
  const {
    plans,
    summary,
    generatePlan,
  } = useProductionAllocation()

  return (
    <>
      <PageHeader
        title="Production Allocation"
        subtitle="Optimize production quantities to maximize profit."
      />

      <GeneratePlanButton
        onGenerate={generatePlan}
      />

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
              <ProductionPlanTable plans={plans} />
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
    </>
  )
}

export default ProductionAllocationPage
import { Box } from '@mantine/core'

import PageHeader from '../../components/common/PageHeader'
import ChartCard from '../../components/cards/ChartCard'

import OptimizationHistoryChart from './components/OptimizationHistoryChart'
import OptimizationHistoryTable from './components/OptimizationHistoryTable'

import useOptimizationHistory from './hooks/useOptimizationHistory'

const OptimizationHistoryPage = () => {
  const {
    optimizationHistory,
    profitTrendData,
    isLoading,
    isError,
  } = useOptimizationHistory()

  return (
    <>
      <PageHeader
        title="Optimization History"
        subtitle="Historical optimization runs generated through the production planning workflow."
      />

      <ChartCard
        title="Optimization History"
        subtitle={`${optimizationHistory.length} optimization runs`}
      >
        <OptimizationHistoryTable
          optimizationHistory={
            optimizationHistory
          }
          isLoading={isLoading}
          isError={isError}
        />
      </ChartCard>

      <Box mt="md">
        <ChartCard
            title="Projected Profit Trends from Optimization Runs"
        >
            <OptimizationHistoryChart
                data={profitTrendData}
                isLoading={isLoading}
                isError={isError}
            />
        </ChartCard>
      </Box>
    </>
  )
}

export default OptimizationHistoryPage

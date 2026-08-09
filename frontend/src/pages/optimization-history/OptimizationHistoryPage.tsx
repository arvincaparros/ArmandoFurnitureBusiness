import PageHeader from '../../components/common/PageHeader'
import ChartCard from '../../components/cards/ChartCard'

import OptimizationHistoryChart from './components/OptimizationHistoryChart'
import OptimizationHistoryTable from './components/OptimizationHistoryTable'
import OptimizationToolbar from './components/OptimizationToolbar'

import useOptimizationHistory from './hooks/useOptimizationHistory'
import { Box } from '@mantine/core'

const OptimizationHistoryPage = () => {
  const {
    optimizationHistory,
    profitTrendData,
  } = useOptimizationHistory()

  const handleRunOptimization = () => {
    console.log('Run manual optimization')
  }

  return (
    <>
      <PageHeader
        title="Optimization History"
        subtitle="Stored previous optimization results and projected profit trends for future reference"
      />

      <OptimizationToolbar
        onRunOptimization={
          handleRunOptimization
        }
      />

      <ChartCard
        title="Optimization History"
        subtitle={`${optimizationHistory.length} optimization runs`}
      >
        <OptimizationHistoryTable
          optimizationHistory={
            optimizationHistory
          }
        />
      </ChartCard>

      <Box mt="md">
        <ChartCard
            title="Projected Profit Trends from Optimization Runs"
        >
            <OptimizationHistoryChart
                data={profitTrendData}
            />
        </ChartCard>
      </Box>
    </>
  )
}

export default OptimizationHistoryPage
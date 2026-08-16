import { Alert, Box } from '@mantine/core'
import { AlertCircle } from 'lucide-react'

import PageHeader from '../../components/common/PageHeader'
import ChartCard from '../../components/cards/ChartCard'

import OptimizationHistoryChart from './components/OptimizationHistoryChart'
import OptimizationHistoryTable from './components/OptimizationHistoryTable'
import OptimizationToolbar from './components/OptimizationToolbar'

import useOptimizationHistory from './hooks/useOptimizationHistory'

import { getApiErrorMessage } from '../../api/apiError'
import { notify } from '../../utils/notify'

const OptimizationHistoryPage = () => {
  const {
    optimizationHistory,
    profitTrendData,
    isLoading,
    isError,
    hasCycle,
    isCycleLoading,
    runOptimization,
    isRunning,
    runError,
  } = useOptimizationHistory()

  const handleRunOptimization = async () => {
    try {
      await runOptimization()

      notify.generated()
    } catch {
      // Failure is surfaced via runError below - existing history
      // stays exactly as it was, no fake success toast.
    }
  }

  return (
    <>
      <PageHeader
        title="Optimization History"
        subtitle="Stored previous optimization results and projected profit trends for future reference"
      />

      <OptimizationToolbar
        onRunOptimization={() => {
          void handleRunOptimization()
        }}
        loading={isRunning}
        disabled={
          !hasCycle || isCycleLoading || isRunning
        }
      />

      {runError && (
        <Alert
          color="red"
          icon={<AlertCircle size={18} />}
          mb="md"
        >
          {getApiErrorMessage(
            runError,
            'Unable to generate a new optimization run. Please try again.',
          )}
        </Alert>
      )}

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

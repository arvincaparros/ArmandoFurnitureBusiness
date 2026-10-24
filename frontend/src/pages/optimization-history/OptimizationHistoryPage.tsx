import { useState } from 'react'

import {
  Box,
  Button,
  Group,
  Text,
} from '@mantine/core'

import PageHeader from '../../components/common/PageHeader'
import ChartCard from '../../components/cards/ChartCard'

import OptimizationHistoryChart from './components/OptimizationHistoryChart'
import OptimizationHistoryTable from './components/OptimizationHistoryTable'

import useOptimizationHistory from './hooks/useOptimizationHistory'

const PAGE_SIZE = 10

const OptimizationHistoryPage = () => {
  const {
    optimizationHistory,
    profitTrendData,
    isLoading,
    isError,
  } = useOptimizationHistory()

  // The history endpoint returns the full newest-first dataset, so
  // pagination stays client-side. Page state is stamped with the
  // dataset size: once a refetch changes the dataset (for example a
  // newly generated run), the page falls back to 1 without an effect.
  const [pagination, setPagination] = useState({
    page: 1,
    runCount: optimizationHistory.length,
  })

  const totalPages = Math.max(
    1,
    Math.ceil(optimizationHistory.length / PAGE_SIZE),
  )

  const datasetChanged = pagination.runCount !== optimizationHistory.length

  const currentPage = datasetChanged
    ? 1
    : Math.min(pagination.page, totalPages)

  const pageHistory = optimizationHistory.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE,
  )

  const goToPage = (page: number) => {
    setPagination({
      page,
      runCount: optimizationHistory.length,
    })
  }

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
          optimizationHistory={pageHistory}
          isLoading={isLoading}
          isError={isError}
        />

        {totalPages > 1 && (
          <Group justify="space-between" mt="md">
            <Text size="sm" c="dimmed">
              Page {currentPage} of {totalPages}
            </Text>

            <Group gap="xs">
              <Button
                variant="default"
                size="sm"
                disabled={currentPage === 1}
                onClick={() => goToPage(currentPage - 1)}
              >
                Previous
              </Button>

              <Button
                variant="default"
                size="sm"
                disabled={currentPage === totalPages}
                onClick={() => goToPage(currentPage + 1)}
              >
                Next
              </Button>
            </Group>
          </Group>
        )}
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

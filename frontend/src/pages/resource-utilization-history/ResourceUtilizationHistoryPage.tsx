import { useState } from 'react'

import {
  Button,
  Group,
  Text,
} from '@mantine/core'

import PageHeader from '../../components/common/PageHeader'
import ChartCard from '../../components/cards/ChartCard'

import UtilizationHistoryTable from './components/UtilizationHistoryTable'

import useResourceUtilizationHistory from './hooks/useResourceUtilizationHistory'

const PAGE_SIZE = 15

const ResourceUtilizationHistoryPage = () => {
  const { rows, isLoading, isError } =
    useResourceUtilizationHistory()

  const runCount = new Set(
    rows.map((row) => row.utilizationNumber),
  ).size

  // The hook already returns the full newest-first dataset (one row
  // per resource within a snapshot), so pagination stays client-side.
  // Page state is stamped with the dataset size: once a refetch
  // changes the dataset, the page falls back to 1 without an effect.
  const [pagination, setPagination] = useState({
    page: 1,
    rowCount: rows.length,
  })

  const totalPages = Math.max(
    1,
    Math.ceil(rows.length / PAGE_SIZE),
  )

  const datasetChanged = pagination.rowCount !== rows.length

  const currentPage = datasetChanged
    ? 1
    : Math.min(pagination.page, totalPages)

  const pageRows = rows.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE,
  )

  const goToPage = (page: number) => {
    setPagination({
      page,
      rowCount: rows.length,
    })
  }

  return (
    <>
      <PageHeader
        title="Resource Utilization History"
        subtitle="Historical resource utilization snapshots from applied production plans."
      />

      <ChartCard
        title="Resource Utilization History"
        subtitle={`${runCount} snapshot${runCount === 1 ? '' : 's'} - created only when a production plan is applied`}
      >
        <UtilizationHistoryTable
          rows={pageRows}
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
    </>
  )
}

export default ResourceUtilizationHistoryPage

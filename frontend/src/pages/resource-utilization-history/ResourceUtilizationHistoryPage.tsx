import PageHeader from '../../components/common/PageHeader'
import ChartCard from '../../components/cards/ChartCard'

import UtilizationHistoryTable from './components/UtilizationHistoryTable'

import useResourceUtilizationHistory from './hooks/useResourceUtilizationHistory'

const ResourceUtilizationHistoryPage = () => {
  const { rows, isLoading, isError } =
    useResourceUtilizationHistory()

  const runCount = new Set(
    rows.map((row) => row.utilizationNumber),
  ).size

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
          rows={rows}
          isLoading={isLoading}
          isError={isError}
        />
      </ChartCard>
    </>
  )
}

export default ResourceUtilizationHistoryPage

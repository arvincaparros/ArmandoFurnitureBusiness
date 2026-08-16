import { ScrollArea } from '@mantine/core'
import ChartCard from '../../../components/cards/ChartCard'
import AppTable from '../../../components/tables/AppTable'

import type { DashboardRecommendation } from '../api/dashboardAdapter'

const columns = [
  {
    accessor: 'name',
    title: 'Furniture Name',
  },
  {
    accessor: 'quantity',
    title: 'Recommended Quantity',
  },
  {
    accessor: 'profit',
    title: 'Expected Profit',
  },
]

interface DashboardRecommendationsProps {
  recommendations: DashboardRecommendation[]
  isLoading: boolean
  isError: boolean
}

const DashboardRecommendations = ({
  recommendations,
  isLoading,
  isError,
}: DashboardRecommendationsProps) => {
  const emptyMessage = isLoading
    ? 'Loading recommendations...'
    : isError
      ? 'Unable to load production recommendations.'
      : 'No optimization run has been generated yet.'

  return (
    <ChartCard
      title="Production Recommendations"
      subtitle="Suggested production plan"
    >
      <ScrollArea type="auto" offsetScrollbars>
        <AppTable
          columns={columns}
          data={isLoading ? [] : recommendations}
          emptyMessage={emptyMessage}
        />
      </ScrollArea>

    </ChartCard>
  )
}

export default DashboardRecommendations

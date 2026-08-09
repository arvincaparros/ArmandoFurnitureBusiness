import { ScrollArea } from '@mantine/core'
import ChartCard from '../../../components/cards/ChartCard'
import AppTable from '../../../components/tables/AppTable'

import { productionRecommendations } from '../mock/dashboardData'

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

const DashboardRecommendations = () => {
  return (
    <ChartCard
      title="Production Recommendations"
      subtitle="Suggested production plan"
    >
      <ScrollArea type="auto" offsetScrollbars>
        <AppTable
          columns={columns}
          data={productionRecommendations}
        />
      </ScrollArea>
     
    </ChartCard>
  )
}

export default DashboardRecommendations
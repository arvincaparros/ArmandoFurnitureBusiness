import PageHeader from '../../components/common/PageHeader'

import DashboardCharts from './components/DashboardCharts'
import DashboardStats from './components/DashboardStats'

const DashboardPage = () => {
  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Production overview and analytics"
      />

      <DashboardStats />

      <DashboardCharts />
    </>
  )
}

export default DashboardPage
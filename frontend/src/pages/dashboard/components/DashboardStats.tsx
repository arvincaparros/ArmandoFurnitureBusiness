import { Alert, Grid, Skeleton } from '@mantine/core'
import { AlertCircle } from 'lucide-react'

import StatCard from '../../../components/cards/StatCard'

import type { DashboardStat } from '../types'

interface DashboardStatsProps {
  stats: DashboardStat[]
  isLoading: boolean
  isError: boolean
}

const DashboardStats = ({
  stats,
  isLoading,
  isError,
}: DashboardStatsProps) => {
  if (isError) {
    return (
      <Alert
        color="red"
        icon={<AlertCircle size={18} />}
        mb="sm"
      >
        Unable to load dashboard statistics.
      </Alert>
    )
  }

  return (
    <Grid mb="sm">
      {(isLoading ? Array.from({ length: 4 }) : stats).map(
        (stat, index) => (
          <Grid.Col
            key={
              isLoading
                ? index
                : (stat as DashboardStat).id
            }
            span={{ base: 12, md: 6, lg: 3 }}
          >
            {isLoading || !stat ? (
              <Skeleton height={104} radius="lg" />
            ) : (
              <StatCard
                title={(stat as DashboardStat).title}
                value={(stat as DashboardStat).value}
                icon={(stat as DashboardStat).icon}
                color={(stat as DashboardStat).color}
              />
            )}
          </Grid.Col>
        ),
      )}
    </Grid>
  )
}

export default DashboardStats

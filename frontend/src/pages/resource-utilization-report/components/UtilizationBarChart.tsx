import { Card, Center, Loader, Text } from '@mantine/core'

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { UtilizationResource } from '../types'

import { UTILIZATION_STATUS_META } from '../utilizationStatus'

interface UtilizationBarChartProps {
  resources: UtilizationResource[]
  isLoading: boolean
  isError: boolean
}

const UtilizationBarChart = ({
  resources,
  isLoading,
  isError,
}: UtilizationBarChartProps) => {
  return (
    <Card withBorder radius="lg" shadow="sm">
      <Text fw={600} mb="md">
        Resource Utilization by Resource
      </Text>

      {isLoading ? (
        <Center h={220}>
          <Loader />
        </Center>
      ) : isError ? (
        <Center h={220}>
          <Text c="dimmed">
            Unable to load resource utilization.
          </Text>
        </Center>
      ) : resources.length === 0 ? (
        <Center h={220}>
          <Text c="dimmed">
            No utilization data for this production cycle.
          </Text>
        </Center>
      ) : (
      <ResponsiveContainer width="100%" height={Math.max(220, resources.length * 40)}>
        <BarChart
          data={resources}
          layout="vertical"
          margin={{ left: 12, right: 24 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            horizontal={false}
          />

          <XAxis
            type="number"
            domain={[0, 100]}
            unit="%"
          />

          <YAxis
            type="category"
            dataKey="resourceName"
            width={90}
          />

          <Tooltip
            formatter={(value) => `${value}%`}
          />

          <Bar dataKey="utilizationPercent" radius={4}>
            {resources.map((resource) => (
              <Cell
                key={resource.id}
                fill={UTILIZATION_STATUS_META[resource.status].hex}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      )}
    </Card>
  )
}

export default UtilizationBarChart

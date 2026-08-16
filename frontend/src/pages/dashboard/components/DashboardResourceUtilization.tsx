import {
  Card,
  Center,
  Group,
  Loader,
  Menu,
  Text,
} from '@mantine/core'

import { MoreHorizontal } from 'lucide-react'

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

import type { DashboardResourceUtilizationBar } from '../api/dashboardAdapter'

// Matches the severity convention already used by the Resource
// Utilization Report module (red >=90%, amber >=70%, else green).
function barColor(value: number): string {
  if (value >= 90) {
    return '#DC2626'
  }

  if (value >= 70) {
    return '#D97706'
  }

  return '#16A34A'
}

interface DashboardResourceUtilizationProps {
  data: DashboardResourceUtilizationBar[]
  isLoading: boolean
  isError: boolean
}

const DashboardResourceUtilization = ({
  data,
  isLoading,
  isError,
}: DashboardResourceUtilizationProps) => {
  return (
    <Card
      shadow="sm"
      radius="md"
      withBorder
      h="100%"
    >
      <Group justify="space-between" mb="xs">
        <div>
          <Text fw={600} size="lg">
            Resource Utilization
          </Text>

          <Text
            size="sm"
            c="dimmed"
          >
            Current allocation
          </Text>
        </div>

        <Menu>
          <Menu.Target>
            <MoreHorizontal
              size={18}
              style={{ cursor: 'pointer' }}
            />
          </Menu.Target>

          <Menu.Dropdown>
            <Menu.Item>Refresh</Menu.Item>
          </Menu.Dropdown>
        </Menu>
      </Group>

      {isLoading ? (
        <Center h={320}>
          <Loader />
        </Center>
      ) : isError ? (
        <Center h={320}>
          <Text c="dimmed">
            Unable to load resource utilization.
          </Text>
        </Center>
      ) : data.length === 0 ? (
        <Center h={320}>
          <Text c="dimmed">
            No production cycle has been run yet.
          </Text>
        </Center>
      ) : (
        <ResponsiveContainer
          width="100%"
          height={320}
        >
          <BarChart
            data={data}
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
              dataKey="name"
              width={90}
            />

            <Tooltip
              formatter={(value) => `${value}%`}
            />

            <Bar dataKey="value" radius={4}>
              {data.map((entry, index) => (
                <Cell
                  key={index}
                  fill={barColor(entry.value)}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </Card>
  )
}

export default DashboardResourceUtilization

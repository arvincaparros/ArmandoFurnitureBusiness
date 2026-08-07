import {
  Card,
  Group,
  Menu,
  Text,
} from '@mantine/core'

import { MoreHorizontal } from 'lucide-react'

import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from 'recharts'

import { resourceUtilization } from '../mock/dashboardData'

const COLORS = [
  '#2563EB',
  '#16A34A',
  '#EA580C',
  '#0891B2',
  '#A855F7',
]

const DashboardResourceUtilization = () => {
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

      <ResponsiveContainer
        width="100%"
        height={320}
      >
        <PieChart>
          <Pie
            data={resourceUtilization}
            dataKey="value"
            nameKey="name"
            innerRadius={70}
            outerRadius={100}
          >
            {resourceUtilization.map((_, index) => (
              <Cell
                key={index}
                fill={COLORS[index % COLORS.length]}
              />
            ))}
          </Pie>

          <Tooltip />

          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </Card>
  )
}

export default DashboardResourceUtilization
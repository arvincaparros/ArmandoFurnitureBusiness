import {
  Card,
  Group,
  Stack,
  Text,
  Box,
} from '@mantine/core'
import { DonutChart } from '@mantine/charts'
import type { PieChartData } from '../types'

interface UtilizationPieChartProps {
  data: PieChartData[]
}

const UtilizationPieChart = ({
  data,
}: UtilizationPieChartProps) => {
  return (
    <Card withBorder radius="lg" shadow="sm">
      <Stack align="center" gap="lg">
        <Text fw={600}>
          Resource Utilization Pie Chart and Bottleneck Analysis
        </Text>

        <Group gap="lg">
          {data.map((item) => (
            <Group key={item.name} gap={6}>
              <Box
                w={12}
                h={12}
                bg={item.color}
                style={{ borderRadius: 2 }}
              />

              <Text size="sm">
                {item.name} ({item.value}%)
              </Text>
            </Group>
          ))}
        </Group>

        <DonutChart
          data={data}
          size={260}
          thickness={40}
          withLabels
          withLabelsLine
          withTooltip
          tooltipDataSource="segment"
        />
      </Stack>
    </Card>
  )
}

export default UtilizationPieChart
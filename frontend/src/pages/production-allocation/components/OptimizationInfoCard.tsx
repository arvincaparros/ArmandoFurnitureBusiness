import {
  Card,
  Group,
  Stack,
  Text,
} from '@mantine/core'

import type { OptimizationSummary } from '../types'

interface OptimizationInfoCardProps {
  summary: OptimizationSummary | null
}

const OptimizationInfoCard = ({
  summary,
}: OptimizationInfoCardProps) => {
  return (
    <Card
      withBorder
      radius="md"
      p="lg"
    >
      <Text fw={600} mb="md">
        Optimization Info
      </Text>

      <Stack gap="sm">
        <Group justify="space-between">
          <Text c="dimmed">Start</Text>
          <Text>{summary?.startTime ?? '—'}</Text>
        </Group>

        <Group justify="space-between">
          <Text c="dimmed">End</Text>
          <Text>{summary?.endTime ?? '—'}</Text>
        </Group>

        <Group justify="space-between">
          <Text c="dimmed">Duration</Text>
          <Text>{summary?.duration ?? '—'}</Text>
        </Group>
      </Stack>
    </Card>
  )
}

export default OptimizationInfoCard

import {
  Card,
  Grid,
  Group,
  Stack,
  Text,
} from '@mantine/core'

import {
  Gauge,
  Layers3,
  UserRound,
  Cog,
} from 'lucide-react'

import type { UtilizationSummary } from '../types'

interface SummaryCardsProps {
  summary: UtilizationSummary
}

const cards = (
  summary: UtilizationSummary,
) => [
  {
    title: 'Overall Utilization Rate',
    value: `${summary.utilizationRate}%`,
    icon: Gauge,
  },
  {
    title: 'Total Raw Materials Consumed',
    value: `${summary.totalRawMaterials.toLocaleString()} units`,
    icon: Layers3,
  },
  {
    title: 'Total Labor Hours Used',
    value: `${summary.laborUsed} / ${summary.laborCapacity} hrs`,
    icon: UserRound,
  },
  {
    title: 'Total Machine Hours Used',
    value: `${summary.machineUsed} / ${summary.machineCapacity} hrs`,
    icon: Cog,
  },
]

const SummaryCards = ({
  summary,
}: SummaryCardsProps) => {
  return (
    <Grid>
      {cards(summary).map((card) => (
        <Grid.Col
          key={card.title}
          span={{ base: 12, sm: 6, lg: 3 }}
        >
          <Card
            withBorder
            radius="lg"
            shadow="sm"
            h="100%"
          >
            <Group justify="space-between">
              <Stack gap={2}>
                <Text
                  size="xs"
                  c="dimmed"
                  tt="uppercase"
                >
                  {card.title}
                </Text>

                <Text
                  fw={700}
                  size="xl"
                >
                  {card.value}
                </Text>
              </Stack>

              <card.icon
                size={22}
                color="#868E96"
              />
            </Group>
          </Card>
        </Grid.Col>
      ))}
    </Grid>
  )
}

export default SummaryCards
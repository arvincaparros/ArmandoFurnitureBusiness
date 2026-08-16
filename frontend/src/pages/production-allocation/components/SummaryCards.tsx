import {
  Card,
  Stack,
  Text,
  Title,
} from '@mantine/core'

import type { OptimizationSummary } from '../types'

interface SummaryCardsProps {
  summary: OptimizationSummary | null
}

const SummaryCards = ({
  summary,
}: SummaryCardsProps) => {
  const cards = [
    {
      title: 'Total Revenue',
      value: summary?.totalRevenue,
    },
    {
      title: 'Total Cost',
      value: summary?.totalCost,
    },
    {
      title: 'Total Profit',
      value: summary?.totalProfit,
    },
  ]

  return (
    <Stack>
      {cards.map((card) => (
        <Card
          key={card.title}
          withBorder
          radius="md"
          p="lg"
        >
          <Text
            size="xs"
            c="dimmed"
            tt="uppercase"
            fw={600}
          >
            {card.title}
          </Text>

          <Title order={3} mt="xs">
            {card.value === undefined
              ? '—'
              : `₱${card.value.toLocaleString()}`}
          </Title>
        </Card>
      ))}
    </Stack>
  )
}

export default SummaryCards

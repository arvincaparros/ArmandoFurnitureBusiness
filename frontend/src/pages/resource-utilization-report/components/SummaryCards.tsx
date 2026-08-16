import type { ReactNode } from 'react'

import {
  Badge,
  Card,
  Grid,
  Group,
  Skeleton,
  Stack,
  Text,
} from '@mantine/core'

import {
  AlertTriangle,
  Layers3,
  UserRound,
  Cog,
} from 'lucide-react'

import type { UtilizationSummary } from '../types'

import { UTILIZATION_STATUS_META } from '../utilizationStatus'

interface SummaryCardsProps {
  summary: UtilizationSummary | null
  isLoading: boolean
}

interface SummaryCard {
  title: string
  value: string
  detail?: ReactNode
  icon: typeof AlertTriangle
}

// "Overall Utilization Rate" (a blended kg+hours+pcs ratio) and
// "Total Raw Materials Consumed" (a blended kg+pcs quantity labeled
// generic "units") were removed - both summed incompatible units into
// a meaningless number (see the Resource Utilization investigation
// report). Most Constrained Resource (highest individual
// utilization_rate) and Material Resources Used (a count, never a
// summed quantity) are the unit-safe replacements.
const buildCards = (
  summary: UtilizationSummary,
): SummaryCard[] => {
  const mostConstrained = summary.mostConstrained
  const statusMeta = mostConstrained
    ? UTILIZATION_STATUS_META[mostConstrained.status]
    : null

  return [
    {
      title: 'Most Constrained Resource',
      value: mostConstrained
        ? mostConstrained.resourceName
        : 'No resources',
      detail: mostConstrained ? (
        <Group gap={6} mt={2}>
          <Text fw={700} size="xl">
            {mostConstrained.utilizationPercent}%
          </Text>

          {statusMeta && (
            <Badge
              color={statusMeta.color}
              variant="light"
              size="sm"
            >
              {statusMeta.label}
            </Badge>
          )}
        </Group>
      ) : null,
      icon: AlertTriangle,
    },
    {
      title: 'Material Resources Used',
      value: `${summary.materialResourceCount} resource${
        summary.materialResourceCount === 1 ? '' : 's'
      }`,
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
}

const SummaryCards = ({
  summary,
  isLoading,
}: SummaryCardsProps) => {
  if (isLoading || !summary) {
    return (
      <Grid>
        {[0, 1, 2, 3].map((key) => (
          <Grid.Col
            key={key}
            span={{ base: 12, sm: 6, lg: 3 }}
          >
            <Skeleton height={92} radius="lg" />
          </Grid.Col>
        ))}
      </Grid>
    )
  }

  return (
    <Grid>
      {buildCards(summary).map((card) => (
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
            <Group justify="space-between" align="flex-start">
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
                  size={card.detail ? 'md' : 'xl'}
                >
                  {card.value}
                </Text>

                {card.detail}
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

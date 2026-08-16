import {
  Alert,
  Badge,
  Divider,
  Group,
  List,
  Skeleton,
  Stack,
  Text,
} from '@mantine/core'

import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
} from 'lucide-react'

import type { Bottleneck, UtilizationResource } from '../types'

interface BottleneckAlertProps {
  bottlenecks: Bottleneck[]
  atRiskResources: UtilizationResource[]
  // Full resource list - only used to look up each bottleneck's
  // utilization_rate (bottlenecks[] itself doesn't carry it) and to
  // detect a "high, but nothing at-risk/bottleneck yet" state. Both
  // come from the same GET /api/resource-utilization/{cycleId}
  // response as bottlenecks/atRiskResources, just joined here rather
  // than duplicated onto the backend's bottleneck schema.
  resources: UtilizationResource[]
  isLoading: boolean
  isError: boolean
}

const BottleneckAlert = ({
  bottlenecks,
  atRiskResources,
  resources,
  isLoading,
  isError,
}: BottleneckAlertProps) => {
  if (isLoading) {
    return <Skeleton height={140} radius="lg" />
  }

  if (isError) {
    return (
      <Alert
        color="red"
        radius="lg"
        title="Bottleneck Analysis"
        icon={<AlertTriangle size={18} />}
      >
        <Text size="sm">
          Unable to load bottleneck data.
        </Text>
      </Alert>
    )
  }

  const utilizationByResourceId = new Map(
    resources.map((resource) => [
      resource.id,
      resource.utilizationPercent,
    ]),
  )

  const hasBottlenecks = bottlenecks.length > 0
  const hasAtRisk = atRiskResources.length > 0

  const hasHighOnly =
    !hasBottlenecks
    && !hasAtRisk
    && resources.some((resource) => resource.status === 'high')

  // Bottleneck always wins visually over at-risk (a true bottleneck
  // is never hidden just because at-risk resources also exist - both
  // are still shown below, this only decides the alert's overall
  // color/icon/headline).
  const color = hasBottlenecks
    ? 'red'
    : hasAtRisk
      ? 'orange'
      : hasHighOnly
        ? 'yellow'
        : 'green'

  const icon = hasBottlenecks ? (
    <AlertOctagon size={18} />
  ) : hasAtRisk || hasHighOnly ? (
    <AlertTriangle size={18} />
  ) : (
    <CheckCircle2 size={18} />
  )

  const headline = hasBottlenecks
    ? `${bottlenecks.length} bottleneck${
        bottlenecks.length === 1 ? '' : 's'
      } detected.`
    : hasAtRisk
      ? `${atRiskResources.length} resource${
          atRiskResources.length === 1 ? '' : 's'
        } at risk.`
      : hasHighOnly
        ? 'Resources are operating at high utilization.'
        : 'No resource capacity issues for this production cycle.'

  return (
    <Alert
      color={color}
      radius="lg"
      title="Bottleneck Analysis"
      icon={icon}
    >
      <Stack gap="sm">
        <Text size="sm" fw={600}>
          {headline}
        </Text>

        {hasBottlenecks && (
          <List spacing="xs">
            {bottlenecks.map((item) => {
              const utilization = utilizationByResourceId.get(
                item.id,
              )

              return (
                <List.Item key={item.id}>
                  <Group gap="xs">
                    <Text fw={600}>{item.resource}</Text>

                    <Badge
                      color="red"
                      size="sm"
                      variant="light"
                    >
                      {item.isBinding
                        ? 'Fully Utilized'
                        : 'Over Capacity'}
                    </Badge>
                  </Group>

                  <Text size="sm">
                    {utilization !== undefined
                      ? `${utilization}% utilized. `
                      : ''}
                    {item.reason}
                  </Text>

                  {item.shortageQuantity > 0 && (
                    <Text size="sm" c="dimmed">
                      Shortage: {item.shortageQuantity}{' '}
                      {item.unit}
                    </Text>
                  )}
                </List.Item>
              )
            })}
          </List>
        )}

        {hasBottlenecks && hasAtRisk && <Divider />}

        {hasAtRisk && (
          <Stack gap={4}>
            {hasBottlenecks && (
              <Text
                size="xs"
                fw={600}
                c="dimmed"
                tt="uppercase"
              >
                Also at risk
              </Text>
            )}

            <List spacing="xs">
              {atRiskResources.map((item) => (
                <List.Item key={item.id}>
                  <Group gap="xs">
                    <Text fw={600}>
                      {item.resourceName}
                    </Text>

                    <Badge
                      color="orange"
                      size="sm"
                      variant="light"
                    >
                      At Risk
                    </Badge>
                  </Group>

                  <Text size="sm">
                    {item.utilizationPercent}% utilized. Only{' '}
                    {item.totalRemaining} {item.unit} remaining.
                  </Text>
                </List.Item>
              ))}
            </List>
          </Stack>
        )}
      </Stack>
    </Alert>
  )
}

export default BottleneckAlert

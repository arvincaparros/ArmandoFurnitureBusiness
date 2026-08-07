import {
  Card,
  Group,
  Text,
  ActionIcon,
} from '@mantine/core'

import { MoreHorizontal } from 'lucide-react'

interface ChartCardProps {
  title: string
  subtitle?: string
  children: React.ReactNode
  action?: React.ReactNode
}

const ChartCard = ({
  title,
  subtitle,
  children,
  action,
}: ChartCardProps) => {
  return (
    <Card
      withBorder
      radius="lg"
      shadow="xs"
      p="lg"
    >
      <Group justify="space-between" mb="md">
        <div>
          <Text fw={600}>
            {title}
          </Text>

          {subtitle && (
            <Text
              size="sm"
              c="dimmed"
            >
              {subtitle}
            </Text>
          )}
        </div>

        {action ?? (
          <ActionIcon variant="subtle">
            <MoreHorizontal size={18} />
          </ActionIcon>
        )}
      </Group>

      {children}
    </Card>
  )
}

export default ChartCard
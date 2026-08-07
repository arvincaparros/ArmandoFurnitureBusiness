import {
  ActionIcon,
  Card,
  Group,
  Stack,
  Text,
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
      shadow="sm"
      radius="lg"
      p="lg"
      h="100%"
    >
      <Group
        justify="space-between"
        mb="lg"
      >
        <div>
          <Text
            fw={600}
            size="lg"
          >
            {title}
          </Text>

          {subtitle && (
            <Text
              size="sm"
              c="dimmed"
              mt={4}
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

      <Stack
        justify="center"
        h="100%"
      >
        {children}
      </Stack>
    </Card>
  )
}

export default ChartCard
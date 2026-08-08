import type { ReactNode } from 'react'

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
  children: ReactNode
  rightSection?: ReactNode
}

const ChartCard = ({
  title,
  subtitle,
  children,
  rightSection,
}: ChartCardProps) => {
  return (
    <Card
      withBorder
      shadow="sm"
      radius="lg"
      p="lg"
      h="100%"
    >
      <Group justify="space-between" align="flex-start">
        <div>
            <Text fw={700} size="xl">
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

        {rightSection ?? (
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
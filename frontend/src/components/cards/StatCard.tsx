import {
  Card,
  Group,
  Text,
  ThemeIcon,
} from '@mantine/core'

import type { LucideIcon } from 'lucide-react'

interface StatCardProps {
  title: string
  value: string | number
  icon: LucideIcon

  color?: string
}

const StatCard = ({
  title,
  value,
  icon: Icon,
  color = 'blue',
}: StatCardProps) => {
  return (
    <Card
      withBorder
      radius="lg"
      p="lg"
      shadow="xs"
    >
      <Group justify="space-between" mb="xs">
        <Text
          size="sm"
          c="dimmed"
        >
          {title}
        </Text>

        <ThemeIcon
          color={color}
          variant="light"
          size={42}
          radius="md"
        >
          <Icon size={20} />
        </ThemeIcon>
      </Group>

      <Text
        size="1.5rem"
        fw={700}
      >
        {value}
      </Text>
    </Card>
  )
}

export default StatCard
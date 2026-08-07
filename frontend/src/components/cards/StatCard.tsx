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

  description?: string
  color?: string
}

const StatCard = ({
  title,
  value,
  icon: Icon,
  description,
  color = 'blue',
}: StatCardProps) => {
  return (
    <Card
      withBorder
      radius="lg"
      p="lg"
      shadow="xs"
    >
      <Group justify="space-between" mb="md">
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
          <Icon size={22} />
        </ThemeIcon>
      </Group>

      <Text
        size="2rem"
        fw={700}
      >
        {value}
      </Text>

      {description && (
        <Text
          mt="xs"
          size="sm"
          c="dimmed"
        >
          {description}
        </Text>
      )}
    </Card>
  )
}

export default StatCard
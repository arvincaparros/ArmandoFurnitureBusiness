import type { ReactNode } from 'react'

import {
  ActionIcon,
  Card,
  Group,
  Stack,
  Text,
} from '@mantine/core'

import { MoreHorizontal } from 'lucide-react'

import { useThemeMode } from '../../theme/ThemeContext'

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
  const { mode } = useThemeMode()
  const isWood = mode === 'wood'

  return (
    <Card
      withBorder
      shadow="sm"
      radius="lg"
      p="lg"
      h="100%"
      style={
        isWood
          ? {
              backgroundColor: 'var(--card-bg)',
              backgroundImage: 'var(--card-bg-image)',
              borderColor: 'var(--card-border)',
              borderRadius: 14,
              boxShadow: 'var(--card-shadow)',
            }
          : undefined
      }
    >
      <Group justify="space-between" align="flex-start">
        <div>
            <Text
              fw={700}
              size="xl"
              style={
                isWood
                  ? {
                      fontFamily: 'var(--font-heading)',
                      color: 'var(--ink-900)',
                    }
                  : undefined
              }
            >
            {title}
            </Text>

            {subtitle && (
            <Text
                size="sm"
                c={isWood ? undefined : 'dimmed'}
                mt={4}
                style={isWood ? { color: 'var(--ink-400)' } : undefined}
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
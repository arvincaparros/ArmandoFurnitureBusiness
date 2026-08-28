import {
  Card,
  Group,
  Text,
  ThemeIcon,
} from '@mantine/core'

import type { LucideIcon } from 'lucide-react'

import { useThemeMode } from '../../theme/ThemeContext'

interface StatCardProps {
  title: string
  value: string | number
  icon: LucideIcon

  color?: string
}

// Maps the app's existing Mantine color names to the reference
// design's warm icon-badge tones (amber/green/rose/violet), keeping
// each stat's badge distinct without clashing with the wood palette.
const woodBadgeColors: Record<string, { bg: string; fg: string }> = {
  blue: { bg: '#F1DFC2', fg: 'var(--copper-600)' },
  green: { bg: '#DCE7D3', fg: 'var(--sage-500)' },
  orange: { bg: '#F0DCD3', fg: '#9A4A2E' },
  grape: { bg: '#E4DCEE', fg: '#6B4E8E' },
}

const StatCard = ({
  title,
  value,
  icon: Icon,
  color = 'blue',
}: StatCardProps) => {
  const { mode } = useThemeMode()
  const isWood = mode === 'wood'

  const badge = woodBadgeColors[color] ?? woodBadgeColors.blue

  return (
    <Card
      withBorder
      radius="lg"
      p="lg"
      shadow="xs"
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
      <Group justify="space-between" mb="xs">
        <Text
          size="sm"
          c={isWood ? undefined : 'dimmed'}
          style={isWood ? { color: 'var(--ink-400)' } : undefined}
        >
          {title}
        </Text>

        <ThemeIcon
          color={color}
          variant="light"
          size={42}
          radius="md"
          style={
            isWood
              ? { backgroundColor: badge.bg, color: badge.fg }
              : undefined
          }
        >
          <Icon size={20} />
        </ThemeIcon>
      </Group>

      <Text
        size="1.5rem"
        fw={700}
        style={
          isWood
            ? { fontFamily: 'var(--font-heading)', color: 'var(--ink-900)' }
            : undefined
        }
      >
        {value}
      </Text>
    </Card>
  )
}

export default StatCard
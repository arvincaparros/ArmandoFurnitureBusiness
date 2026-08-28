import {
  Group,
  Stack,
  Text,
  ThemeIcon,
} from '@mantine/core'

import { Hammer } from 'lucide-react'

import { useThemeMode } from '../../theme/ThemeContext'

const Logo = () => {
  const { mode } = useThemeMode()
  const isWood = mode === 'wood'

  return (
    <Group gap="sm" wrap="nowrap">
      <ThemeIcon
        size={44}
        radius="md"
        variant={isWood ? 'gradient' : 'light'}
        gradient={
          isWood
            ? { from: '#A16C36', to: '#4A2A17', deg: 155 }
            : undefined
        }
      >
        <Hammer size={22} />
      </ThemeIcon>

      <Stack gap={0}>
        <Text
          fw={700}
          size="md"
          style={
            isWood
              ? { fontFamily: 'var(--font-heading)', color: 'var(--ink-900)' }
              : undefined
          }
        >
          Armando's
        </Text>

        <Text
          size="sm"
          c={isWood ? undefined : 'dimmed'}
          visibleFrom="sm"
          style={isWood ? { color: 'var(--ink-400)' } : undefined}
        >
          Wood Carving Furniture Business
        </Text>
      </Stack>
    </Group>
  )
}

export default Logo

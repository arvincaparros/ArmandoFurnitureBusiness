import { Box, Group, Text } from '@mantine/core'

import { useThemeMode } from '../../theme/ThemeContext'

interface PageHeaderProps {
  title: string
  subtitle?: string
  rightSection?: React.ReactNode
}

const PageHeader = ({
  title,
  subtitle,
  rightSection,
}: PageHeaderProps) => {
  const { mode } = useThemeMode()
  const isWood = mode === 'wood'

  return (
    <Group justify="space-between" mb="sm">
      <Box>
        <Text
          size="1.5rem"
          fw={700}
          style={
            isWood
              ? { fontFamily: 'var(--font-heading)', color: 'var(--ink-900)' }
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
      </Box>

      {rightSection && (
        <Box>
          {rightSection}
        </Box>
      )}
    </Group>
  )
}

export default PageHeader
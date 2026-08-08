import { Box, Group, Text } from '@mantine/core'

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
  return (
    <Group justify="space-between" mb="sm">
      <Box>
        <Text
          size="1.5rem"
          fw={700}
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
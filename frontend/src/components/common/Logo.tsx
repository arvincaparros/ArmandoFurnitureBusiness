import {
  Group,
  Stack,
  Text,
  ThemeIcon,
} from '@mantine/core'

import { Hammer } from 'lucide-react'

const Logo = () => {
  return (
    <Group gap="sm" wrap="nowrap">
      <ThemeIcon
        size={44}
        radius="md"
        variant="light"
      >
        <Hammer size={22} />
      </ThemeIcon>

      <Stack gap={0}>
        <Text fw={700} size="md">
          Armando's
        </Text>

        <Text
          size="sm"
          c="dimmed"
          visibleFrom="sm"
        >
          Wood Carving Furniture Business
        </Text>
      </Stack>
    </Group>
  )
}

export default Logo
import { Group, Text, ThemeIcon } from '@mantine/core'
import { Package } from 'lucide-react'

const Logo = () => {
  return (
    <Group gap="sm">
      <ThemeIcon
        size={42}
        radius="md"
        variant="light"
      >
        <Package size={22} />
      </ThemeIcon>

      <div>
        <Text fw={700}>
          Armando's
        </Text>

        <Text
          size="sm"
          c="dimmed"
        >
          Wood Carving Furniture Business
        </Text>
      </div>
    </Group>
  )
}

export default Logo
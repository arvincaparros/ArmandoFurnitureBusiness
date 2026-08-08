import {
  Box,
  Button,
  Card,
  Flex,
  Stack,
  Text,
} from '@mantine/core'

import {
  Boxes,
  Package,
  Factory,
  FileBarChart,
  History,
} from 'lucide-react'

const actions = [
  {
    title: 'Manage Resources',
    icon: Boxes,
  },
  {
    title: 'Manage Products Data',
    icon: Package,
  },
  {
    title: 'Generate Product Plan',
    icon: Factory,
  },
  {
    title: 'View Reports',
    icon: FileBarChart,
  },
  {
    title: 'View History',
    icon: History,
  },
]

const DashboardQuickActions = () => {
  return (
    <Card
      withBorder
      radius="md"
      p="md"
    >
      <Stack gap="xs">
        <Text fw={600}>
          Quick Actions
        </Text>

        <Flex gap="md">
          {actions.map((action) => {
            const Icon = action.icon

            return (
              <Box
                key={action.title}
                flex={1}
              >
                <Card
                  withBorder
                  radius="md"
                  p="sm"
                >
                  <Button
                    variant="subtle"
                    fullWidth
                    leftSection={<Icon size={18} />}
                  >
                    {action.title}
                  </Button>
                </Card>
              </Box>
            )
          })}
        </Flex>
      </Stack>
    </Card>
  )
}

export default DashboardQuickActions
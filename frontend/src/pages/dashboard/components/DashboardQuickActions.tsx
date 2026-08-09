import {
  Box,
  Button,
  Card,
  Grid,
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
    <Card withBorder radius="md" p="md">
      <Stack gap="md">
        <Text fw={600}>
          Quick Actions
        </Text>

        <Grid>
          {actions.map((action) => {
            const Icon = action.icon

            return (
              <Grid.Col
                key={action.title}
                span={{
                  base: 6,
                  sm: 4,
                  md: 2.4,
                }}
              >
                <Box h="100%">
                  <Card
                    withBorder
                    radius="md"
                    p="sm"
                    h="100%"
                  >
                    <Button
                      variant="subtle"
                      fullWidth
                      leftSection={
                        <Icon size={18} />
                      }
                      styles={{
                        root: {
                          height: '100%',
                          minHeight: 42,
                        },
                      }}
                    >
                      {action.title}
                    </Button>
                  </Card>
                </Box>
              </Grid.Col>
            )
          })}
        </Grid>
      </Stack>
    </Card>
  )
}


export default DashboardQuickActions
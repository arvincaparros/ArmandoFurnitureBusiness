import { Card, Grid, Button } from '@mantine/core'
import {
  Boxes,
  Package,
  Factory,
  FileBarChart,
} from 'lucide-react'

const actions = [
  {
    title: 'Manage Resources',
    icon: Boxes,
  },
  {
    title: 'Manage Products',
    icon: Package,
  },
  {
    title: 'Generate Plan',
    icon: Factory,
  },
  {
    title: 'Reports',
    icon: FileBarChart,
  },
]

const DashboardQuickActions = () => {
  return (
    <Grid>
      {actions.map((action) => {
        const Icon = action.icon

        return (
          <Grid.Col
            key={action.title}
            span={{ base: 12, sm: 6, lg: 3 }}
          >
            <Card withBorder shadow="xs" radius="md">
              <Button
                variant="subtle"
                fullWidth
                leftSection={<Icon size={18} />}
              >
                {action.title}
              </Button>
            </Card>
          </Grid.Col>
        )
      })}
    </Grid>
  )
}

export default DashboardQuickActions
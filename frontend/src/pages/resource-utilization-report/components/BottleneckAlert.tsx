import {
  Alert,
  List,
  Stack,
  Text,
} from '@mantine/core'

import { AlertTriangle } from 'lucide-react'

import type { Bottleneck } from '../types'

interface BottleneckAlertProps {
  bottlenecks: Bottleneck[]
}

const BottleneckAlert = ({
  bottlenecks,
}: BottleneckAlertProps) => {
  return (
    <Alert
      color="red"
      radius="lg"
      title="Bottleneck Analysis"
      icon={<AlertTriangle size={18} />}
    >
      <Stack gap="xs">
        <List spacing="xs">
          {bottlenecks.map((item) => (
            <List.Item
              key={item.id}
            >
              <Text fw={600}>
                {item.resource}
              </Text>

              <Text size="sm">
                {item.reason}
              </Text>

              <Text
                size="sm"
                c="dimmed"
              >
                Recommendation:{' '}
                {item.recommendation}
              </Text>
            </List.Item>
          ))}
        </List>
      </Stack>
    </Alert>
  )
}

export default BottleneckAlert
import {
  Button,
  Group,
} from '@mantine/core'

import { Play } from 'lucide-react'

interface OptimizationToolbarProps {
  onRunOptimization: () => void
}

const OptimizationToolbar = ({
  onRunOptimization,
}: OptimizationToolbarProps) => {
  return (
    <Group justify="flex-end" mb="md">
      <Button
        leftSection={<Play size={18} />}
        onClick={onRunOptimization}
      >
        Run Manual Optimization
      </Button>
    </Group>
  )
}

export default OptimizationToolbar
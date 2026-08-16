import {
  Button,
  Group,
  Tooltip,
} from '@mantine/core'

import { Play } from 'lucide-react'

interface OptimizationToolbarProps {
  onRunOptimization: () => void
  loading: boolean
  disabled: boolean
}

const OptimizationToolbar = ({
  onRunOptimization,
  loading,
  disabled,
}: OptimizationToolbarProps) => {
  const button = (
    <Button
      leftSection={<Play size={18} />}
      onClick={onRunOptimization}
      loading={loading}
      disabled={disabled}
    >
      Run Manual Optimization
    </Button>
  )

  return (
    <Group justify="flex-end" mb="md">
      {disabled && !loading ? (
        <Tooltip label="No production cycle exists yet.">
          <span>{button}</span>
        </Tooltip>
      ) : (
        button
      )}
    </Group>
  )
}

export default OptimizationToolbar

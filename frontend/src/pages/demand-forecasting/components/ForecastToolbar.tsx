import { Button, Group } from '@mantine/core'
import { Sparkles } from 'lucide-react'

interface ForecastToolbarProps {
  onRunOptimization: () => void
}

const ForecastToolbar = ({
  onRunOptimization,
}: ForecastToolbarProps) => {
  return (
    <Group justify="flex-end" mb="xs">
      <Button
        leftSection={<Sparkles size={18} />}
        onClick={onRunOptimization}
      >
        Run Demand Optimization
      </Button>
    </Group>
  )
}

export default ForecastToolbar
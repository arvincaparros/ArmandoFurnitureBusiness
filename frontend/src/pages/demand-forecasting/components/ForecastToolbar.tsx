import { Button, Group } from '@mantine/core'
import { Sparkles } from 'lucide-react'

interface ForecastToolbarProps {
  onRunForecast: () => void
  loading: boolean
}

const ForecastToolbar = ({
  onRunForecast,
  loading,
}: ForecastToolbarProps) => {
  return (
    <Group justify="flex-end" mb="xs">
      <Button
        leftSection={<Sparkles size={18} />}
        onClick={onRunForecast}
        loading={loading}
        disabled={loading}
      >
        Run Demand Forecast
      </Button>
    </Group>
  )
}

export default ForecastToolbar
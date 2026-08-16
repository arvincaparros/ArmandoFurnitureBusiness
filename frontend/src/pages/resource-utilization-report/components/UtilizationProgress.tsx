import {
  Progress,
  Text,
} from '@mantine/core'

import type { UtilizationStatus } from '../utilizationStatus'
import { UTILIZATION_STATUS_META } from '../utilizationStatus'

interface UtilizationProgressProps {
  value: number
  status: UtilizationStatus
}

const UtilizationProgress = ({
  value,
  status,
}: UtilizationProgressProps) => {
  const color = UTILIZATION_STATUS_META[status].color

  return (
    <>
      <Progress
        value={value}
        color={color}
        radius="xl"
      />

      <Text
        size="xs"
        ta="center"
        mt={4}
      >
        {value.toFixed(1)}%
      </Text>
    </>
  )
}

export default UtilizationProgress
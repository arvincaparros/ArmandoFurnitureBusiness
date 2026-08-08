import {
  Progress,
  Text,
} from '@mantine/core'

interface UtilizationProgressProps {
  value: number
}

const UtilizationProgress = ({
  value,
}: UtilizationProgressProps) => {
  const color =
    value >= 90
      ? 'red'
      : value >= 70
        ? 'yellow'
        : 'green'

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
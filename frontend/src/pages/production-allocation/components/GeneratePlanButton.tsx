import { Button, Tooltip } from '@mantine/core'
import { Cog } from 'lucide-react'

interface GeneratePlanButtonProps {
  onGenerate: () => void
  loading: boolean
  disabled: boolean
}

const GeneratePlanButton = ({
  onGenerate,
  loading,
  disabled,
}: GeneratePlanButtonProps) => {
  const button = (
    <Button
      leftSection={<Cog size={18} />}
      onClick={onGenerate}
      loading={loading}
      disabled={disabled}
    >
      Generate Optimal Production Plan
    </Button>
  )

  if (disabled && !loading) {
    return (
      <Tooltip label="No production cycle exists yet.">
        <span>{button}</span>
      </Tooltip>
    )
  }

  return button
}

export default GeneratePlanButton

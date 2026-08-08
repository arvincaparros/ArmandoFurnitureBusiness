import { Button } from '@mantine/core'
import { Cog } from 'lucide-react'

interface GeneratePlanButtonProps {
  onGenerate: () => void
}

const GeneratePlanButton = ({
  onGenerate,
}: GeneratePlanButtonProps) => {
  return (
    <Button
      leftSection={<Cog size={18} />}
      onClick={onGenerate}
    >
      Generate Optimal Production Plan
    </Button>
  )
}

export default GeneratePlanButton
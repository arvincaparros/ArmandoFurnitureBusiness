import { Button, Group } from '@mantine/core'
import { Plus } from 'lucide-react'

interface ResourceToolbarProps {
  onAdd: () => void
}

const ResourceToolbar = ({
  onAdd,
}: ResourceToolbarProps) => {
  return (
    <Group justify="flex-end" mb="md">
      <Button
        leftSection={<Plus size={18} />}
        onClick={onAdd}
      >
        Add Resource
      </Button>
    </Group>
  )
}

export default ResourceToolbar

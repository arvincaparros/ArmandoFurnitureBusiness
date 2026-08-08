import { Button, Group } from '@mantine/core'
import { Plus, Save } from 'lucide-react'

interface ResourceToolbarProps {
  onAdd: () => void
  onSave: () => void
}

const ResourceToolbar = ({
  onAdd,
  onSave,
}: ResourceToolbarProps) => {
  return (
    <Group justify="flex-end" mb="md">
      <Button
        leftSection={<Plus size={18} />}
        onClick={onAdd}
      >
        Add Resource
      </Button>

      <Button
        variant="light"
        leftSection={<Save size={18} />}
        onClick={onSave}
      >
        Save Changes
      </Button>
    </Group>
  )
}

export default ResourceToolbar
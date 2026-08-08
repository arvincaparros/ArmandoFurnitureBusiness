import { Button, Group } from '@mantine/core'
import { Plus, Save } from 'lucide-react'

interface ProductToolbarProps {
  onAdd: () => void
  onSave: () => void
}

const ProductToolbar = ({
  onAdd,
  onSave,
}: ProductToolbarProps) => {
  return (
    <Group justify="flex-end" mb="md">
      <Button
        leftSection={<Plus size={18} />}
        onClick={onAdd}
      >
        Add Product
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

export default ProductToolbar
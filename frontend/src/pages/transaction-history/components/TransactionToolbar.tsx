import {
  Button,
  Group,
  Menu,
} from '@mantine/core'

import {
  ChevronDown,
  Download,
  FileSpreadsheet,
  FileText,
  Plus,
} from 'lucide-react'

interface TransactionToolbarProps {
  onAdd: () => void
  onExportCsv: () => void
  onExportExcel: () => void
}

const TransactionToolbar = ({
  onAdd,
  onExportCsv,
  onExportExcel,
}: TransactionToolbarProps) => {
  return (
    <Group justify="flex-end" mb="md">
      <Button
        leftSection={<Plus size={18} />}
        onClick={onAdd}
      >
        Add Transaction
      </Button>

      <Menu shadow="md" width={180}>
        <Menu.Target>
          <Button
            variant="light"
            leftSection={<Download size={18} />}
            rightSection={<ChevronDown size={16} />}
          >
            Export
          </Button>
        </Menu.Target>

        <Menu.Dropdown>
          <Menu.Item
            leftSection={<FileText size={16} />}
            onClick={onExportCsv}
          >
            Export as CSV
          </Menu.Item>

          <Menu.Item
            leftSection={
              <FileSpreadsheet size={16} />
            }
            onClick={onExportExcel}
          >
            Export as Excel
          </Menu.Item>
        </Menu.Dropdown>
      </Menu>
    </Group>
  )
}

export default TransactionToolbar
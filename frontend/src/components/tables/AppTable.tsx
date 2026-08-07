import { Table } from '@mantine/core'

interface Column {
  accessor: string
  title: string
}

interface AppTableProps<T> {
  columns: Column[]
  data: T[]
}

const AppTable = <T extends Record<string, unknown>>({
  columns,
  data,
}: AppTableProps<T>) => {
  return (
    <Table
      striped
      highlightOnHover
      withTableBorder
      withColumnBorders
      verticalSpacing="sm"
    >
      <Table.Thead>
        <Table.Tr>
          {columns.map((column) => (
            <Table.Th key={column.accessor}>
              {column.title}
            </Table.Th>
          ))}
        </Table.Tr>
      </Table.Thead>

      <Table.Tbody>
        {data.map((row, index) => (
          <Table.Tr key={index}>
            {columns.map((column) => (
              <Table.Td key={column.accessor}>
                {String(row[column.accessor])}
              </Table.Td>
            ))}
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  )
}

export default AppTable
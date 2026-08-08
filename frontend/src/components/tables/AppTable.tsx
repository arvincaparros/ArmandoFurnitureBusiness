import type { ReactNode } from 'react'

import {
  Group,
  Table,
  Text,
} from '@mantine/core'

import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
} from 'lucide-react'

export interface Column<T> {
  accessor: keyof T | string
  title: string
  width?: number | string
  textAlign?: 'left' | 'center' | 'right'
  sortable?: boolean
  render?: (row: T) => ReactNode
}

interface AppTableProps<T extends object> {
  columns: Column<T>[]
  data: T[]

  sortBy?: keyof T | string
  reverse?: boolean
  onSort?: (column: keyof T | string) => void

  emptyMessage?: string
}

const AppTable = <T extends object>({
  columns,
  data,
  sortBy,
  reverse,
  onSort,
  emptyMessage = 'No data available.',
}: AppTableProps<T>) => {
  const getSortIcon = (
    accessor: keyof T | string,
  ) => {
    if (sortBy !== accessor) {
      return <ArrowUpDown size={14} />
    }

    return reverse ? (
      <ArrowDown size={14} />
    ) : (
      <ArrowUp size={14} />
    )
  }

  return (
    <Table
      striped
      highlightOnHover
      withTableBorder
    >
      <Table.Thead>
        <Table.Tr>
          {columns.map((column) => (
            <Table.Th
              key={String(column.accessor)}
              w={column.width}
              style={{
                whiteSpace: 'nowrap',
                textAlign: column.textAlign,
                cursor: column.sortable
                  ? 'pointer'
                  : 'default',
              }}
              onClick={() => {
                if (
                  column.sortable &&
                  onSort
                ) {
                  onSort(column.accessor)
                }
              }}
            >
              {column.sortable ? (
                <Group
                    gap={10}
                    wrap="nowrap"
                >
                    <Text fw={600}>
                    {column.title}
                    </Text>

                    {getSortIcon(column.accessor)}
                </Group>
                ) : (
                <Text
                    fw={600}
                    ta={column.textAlign}
                >
                    {column.title}
                </Text>
              )}
            </Table.Th>
          ))}
        </Table.Tr>
      </Table.Thead>

      <Table.Tbody>
        {data.length === 0 ? (
          <Table.Tr>
            <Table.Td
              colSpan={columns.length}
              py="xl"
            >
              <Text
                ta="center"
                c="dimmed"
              >
                {emptyMessage}
              </Text>
            </Table.Td>
          </Table.Tr>
        ) : (
          data.map((row, index) => (
            <Table.Tr key={index}>
              {columns.map((column) => (
                <Table.Td
                  key={String(column.accessor)}
                  ta={column.textAlign}
                  style={{
                    whiteSpace: 'nowrap',
                  }}
                >
                    {column.render ? (
                        <Group
                        justify={
                            column.textAlign === 'center'
                            ? 'center'
                            : column.textAlign === 'right'
                                ? 'flex-end'
                                : 'flex-start'
                        }
                        gap={0}
                        wrap="nowrap"
                        >
                        {column.render(row)}
                        </Group>
                    ) : (
                        String(
                        row[column.accessor as keyof T] ?? '',
                        )
                    )}
                </Table.Td>
              ))}
            </Table.Tr>
          ))
        )}
      </Table.Tbody>
    </Table>
  )
}

export default AppTable
import { ScrollArea } from '@mantine/core'
import AppTable, {
  type Column,
} from '../../../components/tables/AppTable'

import type { Transaction } from '../types'

import TransactionRowActions from './TransactionRowActions'

interface TransactionTableProps {
  transactions: Transaction[]
  onEdit: (transaction: Transaction) => void
  onDelete: (transaction: Transaction) => void
  isLoading: boolean
  isError: boolean
  sortBy: keyof Transaction | string
  reverse: boolean
  onSort: (
    accessor: keyof Transaction | string,
  ) => void

  // Only used for the "there are no rows" case. Loading and error
  // messages stay owned by this component.
  emptyMessage?: string
}

const TransactionTable = ({
  transactions,
  onEdit,
  onDelete,
  isLoading,
  isError,
  sortBy,
  reverse,
  onSort,
  emptyMessage,
}: TransactionTableProps) => {
  const columns: Column<Transaction>[] = [
    {
      accessor: 'transactionNumber',
      title: 'Transaction #',
      sortable: true,
    },
    {
      accessor: 'date',
      title: 'Date',
      sortable: true,
    },
    {
      accessor: 'furnitureProduct',
      title: 'Furniture Product',
      sortable: true,
    },
    {
      accessor: 'quantityProduced',
      title: 'Quantity Produced',
      sortable: true,
      textAlign: 'left',
    },
    {
      accessor: 'quantitySold',
      title: 'Sold',
      sortable: true,
      textAlign: 'left',
    },
    {
      accessor: 'salesAmount',
      title: 'Sales',
      sortable: true,
      textAlign: 'left',
      render: (row) =>
        `₱${row.salesAmount.toLocaleString()}`,
    },
    {
      accessor: 'actions',
      title: 'Actions',
      textAlign: 'center',
      render: (row) => (
        <TransactionRowActions
          transaction={row}
          onEdit={onEdit}
          onDelete={onDelete}
        />
      ),
    },
  ]

  const resolvedEmptyMessage = isLoading
    ? 'Loading transactions...'
    : isError
      ? 'Unable to load transactions.'
      : (emptyMessage ?? 'No transactions found.')

  return (
    <ScrollArea
        type="auto"
        offsetScrollbars
    >
        <AppTable
            columns={columns}
            data={isLoading ? [] : transactions}
            sortBy={sortBy}
            reverse={reverse}
            onSort={onSort}
            emptyMessage={resolvedEmptyMessage}
        />
    </ScrollArea>

  )
}

export default TransactionTable
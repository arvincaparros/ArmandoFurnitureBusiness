import { ScrollArea } from '@mantine/core'
import AppTable, {
  type Column,
} from '../../../components/tables/AppTable'

import type { Transaction } from '../types'

interface TransactionTableProps {
  transactions: Transaction[]
  sortBy: keyof Transaction | string
  reverse: boolean
  onSort: (
    accessor: keyof Transaction | string,
  ) => void
}

const TransactionTable = ({
  transactions,
  sortBy,
  reverse,
  onSort,
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
      accessor: 'productionCost',
      title: 'Production Cost',
      sortable: true,
      textAlign: 'left',
      render: (row) =>
        `₱${row.productionCost.toLocaleString()}`,
    },
    {
      accessor: 'profitEarned',
      title: 'Profit Earned',
      sortable: true,
      textAlign: 'left',
      render: (row) => (
        <span
          style={{
            color:
              row.profitEarned >= 0
                ? '#16a34a'
                : '#dc2626',
            fontWeight: 600,
          }}
        >
          ₱{row.profitEarned.toLocaleString()}
        </span>
      ),
    },
  ]

  return (
    <ScrollArea
        type="auto"
        offsetScrollbars
    >
        <AppTable
            columns={columns}
            data={transactions}
            sortBy={sortBy}
            reverse={reverse}
            onSort={onSort}
            emptyMessage="No transactions found."
        />
    </ScrollArea>
    
  )
}

export default TransactionTable
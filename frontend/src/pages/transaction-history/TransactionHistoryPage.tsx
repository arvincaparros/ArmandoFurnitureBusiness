import { useState } from 'react'

import { Search } from 'lucide-react'
import { TextInput } from '@mantine/core'

import PageHeader from '../../components/common/PageHeader'
import ChartCard from '../../components/cards/ChartCard'

import TransactionToolbar from './components/TransactionToolbar'
import TransactionTable from './components/TransactionTable'

import useTransactions from './hooks/useTransactions'
import AddTransactionModal from './components/AddTransactionModal'

import { notify } from '../../utils/notify'
import { exportCsv } from '../../utils/exportCsv'
import { exportExcel } from '../../utils/exportExcel'
import type { Transaction } from './types'

const TransactionHistoryPage = () => {
  const [search, setSearch] = useState('')
  const [opened, setOpened] = useState(false)
  
  const [sortBy, setSortBy] =
    useState<keyof Transaction | string>(
      'transactionNumber',
    )

  const [reverse, setReverse] =
    useState(false)

  const {
    transactions,
    addTransaction,
  } = useTransactions()

  const filteredTransactions =
    transactions.filter(
      (transaction) =>
        transaction.transactionNumber
          .toLowerCase()
          .includes(search.toLowerCase()) ||
        transaction.furnitureProduct
          .toLowerCase()
          .includes(search.toLowerCase()),
    )

  const sortedTransactions = [
    ...filteredTransactions,
  ].sort((a, b) => {
    const aValue = a[
      sortBy as keyof Transaction
    ]

    const bValue = b[
      sortBy as keyof Transaction
    ]

    if (aValue < bValue)
      return reverse ? 1 : -1

    if (aValue > bValue)
      return reverse ? -1 : 1

    return 0
  })

  const handleAddTransaction = (
    transaction: Transaction,
  ) => {
    addTransaction(transaction)

    notify.added('Transaction')

    setOpened(false)
  }

  const handleSort = (
    accessor: keyof Transaction | string,
  ) => {
    if (sortBy === accessor) {
      setReverse((prev) => !prev)
    } else {
      setSortBy(accessor)
      setReverse(false)
    }
  }

  const handleExportCsv = () => {
    exportCsv(
      'transaction-history',
      sortedTransactions.map((t) => ({
        'Transaction Number': t.transactionNumber,
        Date: t.date,
        'Furniture Product': t.furnitureProduct,
        'Quantity Produced': t.quantityProduced,
        'Quantity Sold': t.quantitySold,
        'Sales Amount': t.salesAmount,
        'Production Cost': t.productionCost,
        'Profit Earned': t.profitEarned,
      })),
    )

    notify.exported('CSV')
  }

  const handleExportExcel = async () => {
    await exportExcel(
      'transaction-history',
      sortedTransactions.map((t) => ({
        'Transaction Number':
          t.transactionNumber,
        Date: t.date,
        'Furniture Product':
          t.furnitureProduct,
        'Quantity Produced':
          t.quantityProduced,
        'Quantity Sold':
          t.quantitySold,
        'Sales Amount':
          t.salesAmount,
        'Production Cost':
          t.productionCost,
        'Profit Earned':
          t.profitEarned,
      })),
    )

    notify.exported('Excel')
  }

  return (
    <>
      <PageHeader
        title="Transaction History"
        subtitle="Recording actual production and sales transaction"
      />

      <TransactionToolbar
        onAdd={() => setOpened(true)}
        onExportCsv={handleExportCsv}
        onExportExcel={handleExportExcel}
      />

      <ChartCard
        title="Transactions"
        subtitle={`${filteredTransactions.length} transaction${
          filteredTransactions.length !== 1
            ? 's'
            : ''
        }`}
        rightSection={
          <TextInput
            placeholder="Search transactions..."
            value={search}
            onChange={(e) =>
              setSearch(
                e.currentTarget.value,
              )
            }
            leftSection={
              <Search size={16} />
            }
            w={280}
          />
        }
      >
        <TransactionTable
          transactions={
            sortedTransactions
          }
          sortBy={sortBy}
          reverse={reverse}
          onSort={handleSort}
        />

        <AddTransactionModal
          opened={opened}
          onClose={() => setOpened(false)}
          onSave={handleAddTransaction}
        />
      </ChartCard>
    </>
  )
}

export default TransactionHistoryPage
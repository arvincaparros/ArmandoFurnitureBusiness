import { useState } from 'react'

import { Search } from 'lucide-react'
import { TextInput } from '@mantine/core'

import PageHeader from '../../components/common/PageHeader'
import ChartCard from '../../components/cards/ChartCard'

import TransactionToolbar from './components/TransactionToolbar'
import TransactionTable from './components/TransactionTable'

import useTransactions from './hooks/useTransactions'
import AddTransactionModal from './components/AddTransactionModal'
import DeleteTransactionModal from './components/DeleteTransactionModal'

import { notify } from '../../utils/notify'
import { exportCsv } from '../../utils/exportCsv'
import { exportExcel } from '../../utils/exportExcel'
import type { Transaction } from './types'
import type {
  SalesTransactionCreateRequest,
  SalesTransactionUpdateRequest,
} from './api/transactionTypes'

const TransactionHistoryPage = () => {
  const [search, setSearch] = useState('')
  const [opened, setOpened] = useState(false)

  const [selectedTransaction, setSelectedTransaction] =
    useState<Transaction | null>(null)

  const [deleteOpened, setDeleteOpened] =
    useState(false)

  const [sortBy, setSortBy] =
    useState<keyof Transaction | string>(
      'transactionNumber',
    )

  const [reverse, setReverse] =
    useState(false)

  const {
    transactions,
    isLoading,
    isError,
    products,
    createTransaction,
    updateTransaction,
    deleteTransaction,
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

  const handleSaveTransaction = async (
    data:
      | SalesTransactionCreateRequest
      | SalesTransactionUpdateRequest,
  ) => {
    if (selectedTransaction) {
      await updateTransaction({
        id: selectedTransaction.id,
        data: data as SalesTransactionUpdateRequest,
      })

      notify.updated('Transaction')
    } else {
      await createTransaction(
        data as SalesTransactionCreateRequest,
      )

      notify.added('Transaction')
    }

    setSelectedTransaction(null)
    setOpened(false)
  }

  const handleOpenAdd = () => {
    setSelectedTransaction(null)
    setOpened(true)
  }

  const handleEditTransaction = (
    transaction: Transaction,
  ) => {
    setSelectedTransaction(transaction)
    setOpened(true)
  }

  const handleDeleteTransaction = (
    transaction: Transaction,
  ) => {
    setSelectedTransaction(transaction)
    setDeleteOpened(true)
  }

  const handleConfirmDelete = async () => {
    if (!selectedTransaction) return

    await deleteTransaction({
      id: selectedTransaction.id,
      productId: selectedTransaction.productId,
    })

    notify.deleted('Transaction')

    setDeleteOpened(false)
    setSelectedTransaction(null)
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
        onAdd={handleOpenAdd}
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
          onEdit={handleEditTransaction}
          onDelete={handleDeleteTransaction}
          isLoading={isLoading}
          isError={isError}
          sortBy={sortBy}
          reverse={reverse}
          onSort={handleSort}
        />

        <AddTransactionModal
          opened={opened}
          products={products}
          transaction={selectedTransaction}
          onClose={() => {
            setSelectedTransaction(null)
            setOpened(false)
          }}
          onSave={handleSaveTransaction}
        />

        <DeleteTransactionModal
          opened={deleteOpened}
          transaction={selectedTransaction}
          onClose={() => {
            setDeleteOpened(false)
            setSelectedTransaction(null)
          }}
          onConfirm={handleConfirmDelete}
        />
      </ChartCard>
    </>
  )
}

export default TransactionHistoryPage

import { useState } from 'react'

import { Search } from 'lucide-react'
import { TextInput } from '@mantine/core'

import PageHeader from '../../components/common/PageHeader'
import ChartCard from '../../components/cards/ChartCard'

import TransactionToolbar from './components/TransactionToolbar'
import TransactionTable from './components/TransactionTable'
import TransactionDateRangeFilter from './components/TransactionDateRangeFilter'

import useTransactions from './hooks/useTransactions'
import AddTransactionModal from './components/AddTransactionModal'
import DeleteTransactionModal from './components/DeleteTransactionModal'

import { notify } from '../../utils/notify'
import { exportCsv } from '../../utils/exportCsv'
import { exportExcel } from '../../utils/exportExcel'
import {
  DEFAULT_TRANSACTION_FILTER,
  type Transaction,
  type TransactionFilter,
} from './types'
import {
  isDateOutsideFilter,
  toSubmittedDate,
} from './dateRange'
import type {
  SalesTransactionCreateRequest,
  SalesTransactionUpdateRequest,
} from './api/transactionTypes'

const TransactionHistoryPage = () => {
  const [search, setSearch] = useState('')
  const [opened, setOpened] = useState(false)

  // Defaults to the server-resolved window (the 7 most recent
  // distinct transaction dates). Deliberately not a date range
  // computed here: a client-side default would be anchored to this
  // browser's clock, which goes empty as soon as the data is more
  // than a week old and shifts by a day across timezones.
  const [filter, setFilter] = useState<TransactionFilter>(
    DEFAULT_TRANSACTION_FILTER,
  )

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
    range,
    available,
    isLoading,
    isError,
    products,
    createTransaction,
    updateTransaction,
    deleteTransaction,
  } = useTransactions(filter)

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

  // Describes the window the SERVER applied, not the one requested -
  // the two differ in default mode, where the client never names a
  // range at all.
  const windowLabel = (() => {
    if (!available) {
      return 'no transactions recorded yet'
    }

    if (!range) {
      return 'all transactions'
    }

    if (range.mode === 'latest_available') {
      return `most recent activity - ${range.startDate} to ${range.endDate}`
    }

    if (range.startDate && range.endDate) {
      return `${range.startDate} to ${range.endDate}`
    }

    if (range.startDate) {
      return `${range.startDate} onward`
    }

    if (range.endDate) {
      return `up to ${range.endDate}`
    }

    return 'all transactions'
  })()

  // `available === null` is the only way to tell "this business has
  // recorded nothing yet" apart from "nothing falls in the window you
  // picked" - the second is recoverable with Show All, the first is
  // not, so they must not share a message.
  const emptyMessage = (() => {
    if (!available) {
      return 'No transactions recorded yet. Use Add Transaction to record the first one.'
    }

    if (search.trim() !== '') {
      return 'No transactions match your search in this date range.'
    }

    if (filter.mode === 'all') {
      return 'No transactions found.'
    }

    return 'No transactions in the selected date range. Use Show All to see the full history.'
  })()

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

    // The selected range is deliberately left exactly as the user set
    // it. Widening it automatically to reveal the saved row would
    // silently override a filter they chose; instead the save is
    // reported as succeeded-but-not-visible, and moving the range is
    // left to them.
    const savedDate = toSubmittedDate(data.transaction_date)

    if (isDateOutsideFilter(filter, savedDate) && savedDate) {
      notify.savedOutsideDateRange('Transaction', savedDate)
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

      <TransactionDateRangeFilter
        filter={filter}
        available={available}
        onChange={setFilter}
      />

      <ChartCard
        title="Transactions"
        subtitle={`${filteredTransactions.length} transaction${
          filteredTransactions.length !== 1
            ? 's'
            : ''
        } - ${windowLabel}`}
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
          emptyMessage={emptyMessage}
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

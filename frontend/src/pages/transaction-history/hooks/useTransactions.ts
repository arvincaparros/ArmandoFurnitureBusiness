import { useState } from 'react'

import { transactionData } from '../mock/transactionData'

import type { Transaction } from '../types'

const useTransactions = () => {
  const [transactions, setTransactions] =
    useState<Transaction[]>(transactionData)

  const addTransaction = (
    transaction: Transaction,
  ) => {
    setTransactions((prev) => [
      ...prev,
      transaction,
    ])
  }

  const updateTransaction = (
    updated: Transaction,
  ) => {
    setTransactions((prev) =>
      prev.map((item) =>
        item.id === updated.id
          ? updated
          : item,
      ),
    )
  }

  const deleteTransaction = (
    id: number,
  ) => {
    setTransactions((prev) =>
      prev.filter(
        (item) => item.id !== id,
      ),
    )
  }

  return {
    transactions,
    addTransaction,
    updateTransaction,
    deleteTransaction,
  }
}

export default useTransactions
import type {
  ProductSummary,
  SalesTransactionResponse,
} from './transactionTypes'
import type { Transaction } from '../types'

// Every backend Decimal field arrives as a JSON string, never a bare
// number - see backend/docs/demand-forecasting-api-contract.md §14
// for the same behavior documented on another module.
function parseDecimal(value: string): number {
  const parsed = Number(value)

  return Number.isFinite(parsed) ? parsed : 0
}

// transaction_date is a full ISO datetime ("2026-08-10T10:00:00");
// the UI only ever displays the date portion, matching the existing
// Transaction.date: string (ISO YYYY-MM-DD) contract.
function toUiDate(transactionDate: string): string {
  return transactionDate.split('T')[0]
}

export function toUiTransaction(
  transaction: SalesTransactionResponse,
  productNames: Map<number, string>,
): Transaction {
  return {
    id: transaction.id,
    productId: transaction.product_id,
    transactionNumber: transaction.transaction_number,
    date: toUiDate(transaction.transaction_date),
    furnitureProduct:
      productNames.get(transaction.product_id) ??
      `Product #${transaction.product_id}`,
    quantityProduced: parseDecimal(
      transaction.quantity_produced,
    ),
    quantitySold: parseDecimal(transaction.quantity),
    unitPrice: parseDecimal(transaction.unit_price),
    salesAmount: parseDecimal(transaction.total_sales),
    productionCost: parseDecimal(
      transaction.production_cost,
    ),
    profitEarned: parseDecimal(transaction.total_profit),
  }
}

export function toUiTransactions(
  transactions: SalesTransactionResponse[],
  products: ProductSummary[],
): Transaction[] {
  const productNames = new Map(
    products.map((product) => [product.id, product.name]),
  )

  return transactions.map((transaction) =>
    toUiTransaction(transaction, productNames),
  )
}

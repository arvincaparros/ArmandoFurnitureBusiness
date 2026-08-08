import { useEffect, useState } from 'react'

import {
  Button,
  Group,
  Modal,
  NumberInput,
  Select,
  Stack,
  TextInput,
} from '@mantine/core'

import type { Transaction } from '../types'

interface AddTransactionModalProps {
  opened: boolean
  transaction?: Transaction | null
  onClose: () => void
  onSave: (transaction: Transaction) => void
}

const productOptions = [
  'Dining Table (6-seater)',
  'Dining Table (8-seat)',
  'Ordinary Table',
  'High Chair',
  'Carved Chair',
  'Bed Frame',
  'Door (60x210)',
  'Door (80x210)',
  'Door (90x210)',
]

const AddTransactionModal = ({
  opened,
  transaction,
  onClose,
  onSave,
}: AddTransactionModalProps) => {
  const [transactionNumber, setTransactionNumber] =
    useState('')

  const [date, setDate] = useState('')

  const [furnitureProduct, setFurnitureProduct] =
    useState('')

  const [
    quantityProduced,
    setQuantityProduced,
  ] = useState(0)

  const [quantitySold, setQuantitySold] =
    useState(0)

  const [salesAmount, setSalesAmount] =
    useState(0)

  const [
    productionCost,
    setProductionCost,
  ] = useState(0)

  useEffect(() => {
    if (transaction) {
      setTransactionNumber(
        transaction.transactionNumber,
      )
      setDate(transaction.date)
      setFurnitureProduct(
        transaction.furnitureProduct,
      )
      setQuantityProduced(
        transaction.quantityProduced,
      )
      setQuantitySold(
        transaction.quantitySold,
      )
      setSalesAmount(
        transaction.salesAmount,
      )
      setProductionCost(
        transaction.productionCost,
      )
    } else {
      setTransactionNumber(
        `TRX-${Date.now()}`
      )
      setDate(
        new Date()
          .toISOString()
          .split('T')[0],
      )
      setFurnitureProduct('')
      setQuantityProduced(0)
      setQuantitySold(0)
      setSalesAmount(0)
      setProductionCost(0)
    }
  }, [transaction, opened])

  const handleSave = () => {
    onSave({
      id: transaction?.id ?? Date.now(),
      transactionNumber,
      date,
      furnitureProduct,
      quantityProduced,
      quantitySold,
      salesAmount,
      productionCost,
      profitEarned:
        salesAmount - productionCost,
    })

    onClose()
  }

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        transaction
          ? 'Edit Transaction'
          : 'Add Transaction'
      }
      centered
      size="lg"
      radius="lg"
      styles={{
        content: {
        borderRadius: 16,
        overflow: 'hidden',
        },
      }}
    >
      <Stack>
        <TextInput
          label="Transaction Number"
          value={transactionNumber}
          onChange={(e) =>
            setTransactionNumber(
              e.currentTarget.value,
            )
          }
        />

        <TextInput
          label="Date"
          type="date"
          value={date}
          onChange={(e) =>
            setDate(
              e.currentTarget.value,
            )
          }
        />

        <Select
          label="Furniture Product"
          data={productOptions}
          value={furnitureProduct}
          onChange={(value) =>
            setFurnitureProduct(
              value ?? '',
            )
          }
          searchable
        />

        <NumberInput
          label="Quantity Produced"
          value={quantityProduced}
          onChange={(value) =>
            setQuantityProduced(
              Number(value),
            )
          }
          min={0}
        />

        <NumberInput
          label="Quantity Sold"
          value={quantitySold}
          onChange={(value) =>
            setQuantitySold(
              Number(value),
            )
          }
          min={0}
        />

        <NumberInput
          label="Sales Amount"
          prefix="₱ "
          value={salesAmount}
          onChange={(value) =>
            setSalesAmount(
              Number(value),
            )
          }
          min={0}
        />

        <NumberInput
          label="Production Cost"
          prefix="₱ "
          value={productionCost}
          onChange={(value) =>
            setProductionCost(
              Number(value),
            )
          }
          min={0}
        />

        <NumberInput
          label="Profit Earned"
          value={
            salesAmount -
            productionCost
          }
          prefix="₱ "
          readOnly
        />

        <Group justify="flex-end">
          <Button
            variant="default"
            onClick={onClose}
          >
            Cancel
          </Button>

          <Button onClick={handleSave}>
            Save
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

export default AddTransactionModal
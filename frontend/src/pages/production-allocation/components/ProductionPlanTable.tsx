import {
  Divider,
  Group,
  Text,
} from '@mantine/core'

import AppTable, {
  type Column,
} from '../../../components/tables/AppTable'

import type { ProductionPlan } from '../types'

interface ProductionPlanTableProps {
  plans: ProductionPlan[]
  isLoading: boolean
  isError: boolean
  emptyMessage?: string
}

const ProductionPlanTable = ({
  plans,
  isLoading,
  isError,
  emptyMessage: emptyMessageOverride,
}: ProductionPlanTableProps) => {
  const columns: Column<ProductionPlan>[] = [
    {
      accessor: 'productName',
      title: 'Furniture Type',
    },
    {
      accessor: 'quantity',
      title: 'Quantity to Produce',
      textAlign: 'center',
    },
  ]

  const totalQuantity = plans.reduce(
    (sum, item) => sum + item.quantity,
    0,
  )

  const emptyMessage = isLoading
    ? 'Loading...'
    : isError
      ? 'Unable to load the production plan.'
      : (emptyMessageOverride ??
        'No production plan generated yet. Click "Generate Optimal Production Plan" above.')

  return (
    <>
      <AppTable
        columns={columns}
        data={isLoading ? [] : plans}
        emptyMessage={emptyMessage}
      />

      <Divider my="md" />

      <Group justify="space-between">
        <Text fw={500}>
          Total Furniture Types
        </Text>

        <Text fw={700}>
          {plans.length}
        </Text>
      </Group>

      <Group
        justify="space-between"
        mt="xs"
      >
        <Text fw={500}>
          Total Quantity
        </Text>

        <Text fw={700}>
          {totalQuantity} units
        </Text>
      </Group>
    </>
  )
}

export default ProductionPlanTable

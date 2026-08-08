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
}

const ProductionPlanTable = ({
  plans,
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

  return (
    <>
      <AppTable
        columns={columns}
        data={plans}
        emptyMessage="No production plan generated."
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
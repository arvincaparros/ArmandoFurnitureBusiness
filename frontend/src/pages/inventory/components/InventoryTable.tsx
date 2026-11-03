import { Stack, Text } from '@mantine/core'

import AppTable from '../../../components/tables/AppTable'

import type { Column } from '../../../components/tables/AppTable'
import type { ProductInventory } from '../types'

interface InventoryTableProps {
  products: ProductInventory[]
}

// Column order and headers are fixed: the whole point of this page is
// that "produced this cycle", "sold this cycle" and "available stock"
// are three DIFFERENT quantities, so each is its own labelled column
// rather than one number the reader has to interpret.
const columns: Column<ProductInventory>[] = [
  { accessor: 'productName', title: 'Product' },
  {
    accessor: 'openingQuantity',
    title: 'Opening',
    textAlign: 'right',
  },
  {
    accessor: 'cycleProduced',
    title: 'Produced This Cycle',
    textAlign: 'right',
  },
  {
    accessor: 'cycleSold',
    title: 'Sold This Cycle',
    textAlign: 'right',
  },
  {
    accessor: 'availableStock',
    title: 'Available Stock',
    textAlign: 'right',
    render: (row) => (
      <Text fw={600}>{row.availableStock}</Text>
    ),
  },
]

const InventoryTable = ({ products }: InventoryTableProps) => (
  <Stack gap={4}>
    <Text size="xs" c="dimmed" ta="right">
      Available Stock is across all cycles
    </Text>

    <AppTable
      columns={columns}
      data={products}
      emptyMessage="No products to report stock for yet."
    />
  </Stack>
)

export default InventoryTable

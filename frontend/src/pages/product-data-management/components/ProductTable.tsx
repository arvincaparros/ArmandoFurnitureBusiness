import { Text, ScrollArea } from '@mantine/core'

import AppTable, {
  type Column,
} from '../../../components/tables/AppTable'

import type { Product } from '../types'

interface ProductTableProps {
  products: Product[]
  sortBy: keyof Product | string
  reverse: boolean
  onSort: (
    accessor: keyof Product | string,
  ) => void
}

const ProductTable = ({
  products,
  sortBy,
  reverse,
  onSort,
}: ProductTableProps) => {
  const columns: Column<Product>[] = [
    {
        accessor: 'productName',
        title: 'Furniture',
        sortable: true,
    },
    {
        accessor: 'wood',
        title: 'Wood',
        textAlign: 'center',
    },
    {
        accessor: 'epoxy',
        title: 'Epoxy',
        textAlign: 'center',
    },
    {
        accessor: 'nails',
        title: 'Nails',
        textAlign: 'center',
    },
    {
        accessor: 'glue',
        title: 'Glue',
        textAlign: 'center',
    },
    {
        accessor: 'sandpaper',
        title: 'Sandpaper',
        textAlign: 'center',
    },
    {
        accessor: 'doorknob',
        title: 'Doorknob',
        textAlign: 'center',
    },
    {
        accessor: 'laborHours',
        title: 'Labor Hrs',
        textAlign: 'center',
    },
    {
        accessor: 'sawHours',
        title: 'Saw Hrs',
        textAlign: 'center',
    },
    {
        accessor: 'thicknessPlanerHours',
        title: 'T. Planer',
        textAlign: 'center',
    },
    {
        accessor: 'handPlanerHours',
        title: 'H. Planer',
        textAlign: 'center',
    },
    {
        accessor: 'sellingPrice',
        title: 'Selling Price',
        textAlign: 'right',
        render: (row) =>
        `₱${row.sellingPrice.toLocaleString()}`,
    },
    {
        accessor: 'materialCost',
        title: 'Material',
        textAlign: 'right',
        render: (row) =>
        `₱${row.materialCost.toLocaleString()}`,
    },
    {
        accessor: 'laborCost',
        title: 'Labor',
        textAlign: 'right',
        render: (row) =>
        `₱${row.laborCost.toLocaleString()}`,
    },
    {
        accessor: 'machineCost',
        title: 'Machine',
        textAlign: 'right',
        render: (row) =>
        `₱${row.machineCost.toLocaleString()}`,
    },
    {
        accessor: 'totalCost',
        title: 'Total',
        sortable: true,
        textAlign: 'right',
        render: (row) =>
        `₱${row.totalCost.toLocaleString()}`,
    },
    {
        accessor: 'profit',
        title: 'Profit',
        sortable: true,
        textAlign: 'right',
        render: (row) => (
        <Text
            c={row.profit < 0 ? 'red' : 'green'}
        >
            ₱{row.profit.toLocaleString()}
        </Text>
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
        data={products}
        sortBy={sortBy}
        reverse={reverse}
        onSort={onSort}
        emptyMessage="No products found."
        />
    </ScrollArea>
  )
}

export default ProductTable
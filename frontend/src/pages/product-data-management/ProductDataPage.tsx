import { useState } from 'react'

import { Search } from 'lucide-react'
import { TextInput } from '@mantine/core'

import PageHeader from '../../components/common/PageHeader'
import ChartCard from '../../components/cards/ChartCard'

import ProductToolbar from './components/ProductToolbar'
import ProductTable from './components/ProductTable'
import AddProductModal from './components/AddProductModal'
import DeleteProductModal from './components/DeleteProductModal'

import useProducts from './hooks/useProducts'
import { notify } from '../../utils/notify'
import type { Product } from './types'

const ProductDataPage = () => {
  const [opened, setOpened] = useState(false)

  const [search, setSearch] = useState('')
  
  const [sortBy, setSortBy] = useState<keyof Product>('productName')

  const [reverse, setReverse] = useState(false)

  const [deleteOpened, setDeleteOpened] =
    useState(false)

  const {
    products,
    addProduct,
  } = useProducts()

  const filteredProducts = products.filter((product) =>
    product.productName
      .toLowerCase()
      .includes(search.toLowerCase()),
  )

  const sortedProducts = [...filteredProducts].sort(
    (a, b) => {
      const aValue = a[sortBy]
      const bValue = b[sortBy]

      if (aValue < bValue)
        return reverse ? 1 : -1

      if (aValue > bValue)
        return reverse ? -1 : 1

      return 0
    },
  )

  const handleSort = (
    accessor: keyof Product | string,
  ) => {
    if (sortBy === accessor) {
      setReverse((prev) => !prev)
    } else {
      setSortBy(accessor as keyof Product)
      setReverse(false)
    }
  }

  const handleAddProduct = (product: Product) => {
    addProduct(product)
    notify.added('Product')
  }

  const handleSave = () => {
    notify.saved()
  }

  return (
    <>
      <PageHeader
        title="Product Data Management"
        subtitle="Manage product resource usage, costs, and profit."
      />

      <ProductToolbar
        onAdd={() => setOpened(true)}
        onSave={handleSave}
      />

      <ChartCard
        title="Products"
        subtitle={`Current product list • ${filteredProducts.length} product${
          filteredProducts.length !== 1 ? 's' : ''
        }`}
        rightSection={
          <TextInput
            placeholder="Search products..."
            value={search}
            onChange={(e) =>
              setSearch(e.currentTarget.value)
            }
            leftSection={<Search size={16} />}
            w={260}
          />
        }
      >
        <ProductTable
          products={sortedProducts}
          sortBy={sortBy}
          reverse={reverse}
          onSort={handleSort}
        />
      </ChartCard>

      <AddProductModal
        opened={opened}
        onClose={() => setOpened(false)}
        onSave={handleAddProduct}
      />

      <DeleteProductModal
        opened={deleteOpened}
        product={null}
        onClose={() => setDeleteOpened(false)}
        onConfirm={() => {}}
      />
    </>
  )
}

export default ProductDataPage
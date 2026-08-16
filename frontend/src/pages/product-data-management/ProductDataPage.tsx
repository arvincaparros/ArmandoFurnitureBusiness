import { useState } from 'react'

import { Search } from 'lucide-react'
import { Card, Group, Text, TextInput } from '@mantine/core'

import PageHeader from '../../components/common/PageHeader'

import ProductToolbar from './components/ProductToolbar'
import ProductTable from './components/ProductTable'
import AddProductModal from './components/AddProductModal'
import DeleteProductModal from './components/DeleteProductModal'

import useProducts from './hooks/useProducts'
import { notify } from '../../utils/notify'
import type { Product } from './types'
import type {
  ProductCreateRequest,
  ProductUpdateRequest,
} from './api/productTypes'

import styles from './ProductDataPage.module.css'

const ProductDataPage = () => {
  const [opened, setOpened] = useState(false)

  const [selectedProduct, setSelectedProduct] =
    useState<Product | null>(null)

  const [deleteOpened, setDeleteOpened] =
    useState(false)

  const [search, setSearch] = useState('')

  const [sortBy, setSortBy] = useState<keyof Product>('productName')

  const [reverse, setReverse] = useState(false)

  const {
    products,
    activeResources,
    isLoading,
    isError,
    createProduct,
    updateProduct,
    deleteProduct,
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

      if (aValue === null || bValue === null) {
        return 0
      }

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

  const handleSaveProduct = async (
    payload: ProductCreateRequest | ProductUpdateRequest,
  ) => {
    if (selectedProduct) {
      await updateProduct({
        id: selectedProduct.id,
        data: payload,
      })

      notify.updated(payload.name ?? selectedProduct.productName)
    } else {
      await createProduct(payload as ProductCreateRequest)

      notify.added(payload.name ?? '')
    }

    setSelectedProduct(null)
    setOpened(false)
  }

  const handleEditProduct = (product: Product) => {
    setSelectedProduct(product)
    setOpened(true)
  }

  const handleDeleteProduct = (product: Product) => {
    setSelectedProduct(product)
    setDeleteOpened(true)
  }

  const handleOpenAdd = () => {
    setSelectedProduct(null)
    setOpened(true)
  }

  const handleConfirmDelete = async () => {
    if (!selectedProduct) return

    await deleteProduct(selectedProduct.id)

    notify.deleted(selectedProduct.productName)

    setDeleteOpened(false)
    setSelectedProduct(null)
  }

  const handleSave = () => {
    notify.saved()
  }

  return (
    <>
      <div className={styles.page}>
        <PageHeader
          title="Product Data Management"
          subtitle="Manage product resource usage, costs, and profit."
        />

        <ProductToolbar
          onAdd={handleOpenAdd}
          onSave={handleSave}
        />

        <Card
          withBorder
          shadow="sm"
          radius="lg"
          p="lg"
          className={styles.productsCard}
        >
          <Group
            justify="space-between"
            align="flex-start"
            className={styles.cardHeader}
          >
            <div>
              <Text fw={700} size="xl">
                Products
              </Text>

              <Text size="sm" c="dimmed" mt={4}>
                {`Current product list • ${filteredProducts.length} product${
                  filteredProducts.length !== 1 ? 's' : ''
                }`}
              </Text>
            </div>

            <TextInput
              placeholder="Search products..."
              value={search}
              onChange={(e) =>
                setSearch(e.currentTarget.value)
              }
              leftSection={<Search size={16} />}
              w={260}
            />
          </Group>

          <div className={styles.tableArea}>
            <ProductTable
              products={sortedProducts}
              activeResources={activeResources}
              onEdit={handleEditProduct}
              onDelete={handleDeleteProduct}
              isLoading={isLoading}
              isError={isError}
              sortBy={sortBy}
              reverse={reverse}
              onSort={handleSort}
            />
          </div>
        </Card>
      </div>

      <AddProductModal
        opened={opened}
        product={selectedProduct}
        onClose={() => {
          setSelectedProduct(null)
          setOpened(false)
        }}
        onSave={handleSaveProduct}
      />

      <DeleteProductModal
        opened={deleteOpened}
        product={selectedProduct}
        onClose={() => {
          setDeleteOpened(false)
          setSelectedProduct(null)
        }}
        onConfirm={handleConfirmDelete}
      />
    </>
  )
}

export default ProductDataPage

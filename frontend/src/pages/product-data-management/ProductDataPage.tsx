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
import { exportCsv } from '../../utils/exportCsv'
import { exportExcel } from '../../utils/exportExcel'
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

  // Same product/resource column model ProductTable.tsx renders from
  // (activeResources decides which resource columns exist at all,
  // resourceQuantities is looked up by resource id) - a dynamic
  // resource gaining/losing a column here is a direct consequence of
  // the same activeResources array, never a second, hardcoded list.
  // Cost figures (materialCost/laborCost/machineCost/totalCost/
  // profit) are read straight from each Product - already computed
  // by productAdapter.ts::calculateCosts, never recomputed here.
  // Exports the currently searched + sorted list (sortedProducts) -
  // the same rows visibly rendered in the table - not the full
  // unfiltered product set.
  const buildExportRows = () =>
    sortedProducts.map((product) => {
      const row: Record<string, unknown> = {
        Furniture: product.productName,
      }

      for (const resource of activeResources) {
        const quantity =
          product.resourceQuantities[resource.id]

        // Undefined means genuinely no requirement for this
        // resource on this product (see types.ts) - left blank,
        // never fabricated as 0, matching resourceCell()'s own
        // "—" convention in ProductTable.tsx.
        row[`${resource.name} (${resource.unit})`] =
          quantity === undefined ? '' : quantity
      }

      row['Selling Price'] = product.sellingPrice
      // null means unknown (a required resource has no price
      // configured for the current cycle) - blank, never a
      // misleading 0, matching costCell()'s own "—" convention.
      row['Material'] = product.materialCost ?? ''
      row['Labor'] = product.laborCost ?? ''
      row['Machine'] = product.machineCost ?? ''
      row['Total'] = product.totalCost ?? ''
      row['Profit'] = product.profit ?? ''

      return row
    })

  const handleExportCsv = () => {
    exportCsv('product-data', buildExportRows())

    notify.exported('CSV')
  }

  const handleExportExcel = async () => {
    await exportExcel(
      'product-data',
      buildExportRows(),
      'Products',
    )

    notify.exported('Excel')
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
          onExportCsv={handleExportCsv}
          onExportExcel={handleExportExcel}
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

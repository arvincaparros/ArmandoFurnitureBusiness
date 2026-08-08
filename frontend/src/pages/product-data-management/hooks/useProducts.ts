import { useState } from 'react'

import { productData } from '../mock/productData'

import type { Product } from '../types'

const useProducts = () => {
  const [products, setProducts] =
    useState<Product[]>(productData)

  const addProduct = (product: Product) => {
    setProducts((prev) => [...prev, product])
  }

  const updateProduct = (
    product: Product,
  ) => {
    setProducts((prev) =>
      prev.map((item) =>
        item.id === product.id
          ? product
          : item,
      ),
    )
  }

  const deleteProduct = (id: number) => {
    setProducts((prev) =>
      prev.filter((item) => item.id !== id),
    )
  }

  return {
    products,
    addProduct,
    updateProduct,
    deleteProduct,
  }
}

export default useProducts
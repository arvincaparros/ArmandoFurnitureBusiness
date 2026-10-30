import { render, screen, within } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'
import { describe, expect, it, vi } from 'vitest'

import ProductTable from './ProductTable'

import type { Product } from '../types'
import type { ResourceOption } from '../api/productResourceTypes'

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: 1,
    productName: 'Ordinary Chair',
    sellingPrice: 3500,
    isActive: true,
    resourceQuantities: {},
    minimumDemand: 3,
    materialCost: 500,
    laborCost: 300,
    machineCost: 100,
    totalCost: 900,
    profit: 2600,
    ...overrides,
  }
}

const renderTable = (products: Product[]) => {
  const displayResources: ResourceOption[] = []

  return render(
    <MantineProvider>
      <ProductTable
        products={products}
        displayResources={displayResources}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        isLoading={false}
        isError={false}
        sortBy="productName"
        reverse={false}
        onSort={vi.fn()}
      />
    </MantineProvider>,
  )
}

const rowFor = (name: string) =>
  screen.getByText(name).closest('tr') as HTMLElement

describe('ProductTable Minimum Demand column', () => {
  it('renders a sortable Minimum Demand column header', () => {
    renderTable([makeProduct()])

    expect(screen.getByText('Minimum Demand')).toBeInTheDocument()
  })

  it('displays a positive minimum demand', () => {
    renderTable([makeProduct({ minimumDemand: 3 })])

    expect(
      within(rowFor('Ordinary Chair')).getByText('3'),
    ).toBeInTheDocument()
  })

  it('displays 0 as a literal 0, never a dash', () => {
    renderTable([
      makeProduct({
        productName: 'Dining Table (8 seater)',
        minimumDemand: 0,
      }),
    ])

    const row = rowFor('Dining Table (8 seater)')

    expect(within(row).getByText('0')).toBeInTheDocument()
  })

  it('still displays minimum demand when the cost breakdown is null', () => {
    // An unpriced required resource nulls every cost column, but
    // minimum demand is a stored product field and must still show.
    renderTable([
      makeProduct({
        productName: 'Unpriced Product',
        minimumDemand: 5,
        materialCost: null,
        laborCost: null,
        machineCost: null,
        totalCost: null,
        profit: null,
      }),
    ])

    const row = rowFor('Unpriced Product')

    expect(within(row).getByText('5')).toBeInTheDocument()
  })
})

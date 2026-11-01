import { SimpleGrid } from '@mantine/core'

import { Factory, ShoppingCart, Warehouse } from 'lucide-react'

import StatCard from '../../../components/cards/StatCard'

import type { ProductInventory } from '../types'

interface InventorySummaryCardsProps {
  products: ProductInventory[]
}

const sum = (
  products: ProductInventory[],
  pick: (product: ProductInventory) => number,
) => products.reduce((total, product) => total + pick(product), 0)

// Every card names its own scope in the subtitle. Two of these are
// per-cycle totals that reset when a new cycle starts and one spans
// every cycle; without the scope stated they read as one quantity
// shown three times.
const InventorySummaryCards = ({
  products,
}: InventorySummaryCardsProps) => (
  <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md">
    <StatCard
      title="Produced"
      value={sum(products, (product) => product.cycleProduced)}
      subtitle="this cycle"
      icon={Factory}
      color="blue"
    />

    <StatCard
      title="Sold"
      value={sum(products, (product) => product.cycleSold)}
      subtitle="this cycle"
      icon={ShoppingCart}
      color="orange"
    />

    <StatCard
      title="Available"
      value={sum(products, (product) => product.availableStock)}
      subtitle="all cycles"
      icon={Warehouse}
      color="green"
    />
  </SimpleGrid>
)

export default InventorySummaryCards

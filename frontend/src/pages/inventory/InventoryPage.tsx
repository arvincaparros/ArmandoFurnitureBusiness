import {
  Alert,
  Anchor,
  Card,
  Loader,
  Stack,
  Title,
} from '@mantine/core'

import { AlertTriangle } from 'lucide-react'
import { Link } from 'react-router-dom'

import PageHeader from '../../components/common/PageHeader'

import InventorySummaryCards from './components/InventorySummaryCards'
import InventoryTable from './components/InventoryTable'
import useInventory from './hooks/useInventory'

const formatWindow = (
  start: string | null,
  end: string | null,
) =>
  start && end
    ? `Current cycle ${start.slice(0, 10)} to ${end.slice(0, 10)}`
    : 'No production cycle exists yet'

const InventoryPage = () => {
  const {
    products,
    cycleStartDate,
    cycleEndDate,
    isStockValidationEnabled,
    isLoading,
    isError,
  } = useInventory()

  return (
    <Stack gap="md">
      <PageHeader
        title="Inventory"
        subtitle={formatWindow(cycleStartDate, cycleEndDate)}
      />

      {!isStockValidationEnabled && !isLoading && (
        // Same corrected wording as the Opening Stock page: sales are
        // REFUSED until a complete set is reviewed (Task 23 /
        // Amendment A), not recorded unvalidated.
        <Alert
          color="orange"
          variant="light"
          icon={<AlertTriangle size={18} />}
        >
          Sales cannot be recorded yet, and the figures below have no
          confirmed starting balance behind them. Declare your
          opening stock on{' '}
          <Anchor component={Link} to="/opening-inventory">
            Opening Stock
          </Anchor>{' '}
          and mark the set as reviewed.
        </Alert>
      )}

      {isError && (
        <Alert color="red" icon={<AlertTriangle size={18} />}>
          Unable to load inventory right now.
        </Alert>
      )}

      {isLoading && <Loader size="sm" />}

      {!isLoading && !isError && (
        <>
          <InventorySummaryCards products={products} />

          <Card withBorder radius="lg" shadow="sm" p="lg">
            <Title order={4} mb="md">
              Stock by product
            </Title>

            <InventoryTable products={products} />
          </Card>
        </>
      )}
    </Stack>
  )
}

export default InventoryPage

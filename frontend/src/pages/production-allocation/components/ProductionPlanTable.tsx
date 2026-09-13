import {
  Badge,
  Divider,
  Group,
  ScrollArea,
  Text,
  Tooltip,
} from '@mantine/core'

import AppTable, {
  type Column,
} from '../../../components/tables/AppTable'

import type { ProductionPlan } from '../types'

interface ProductionPlanTableProps {
  plans: ProductionPlan[]
  isLoading: boolean
  isError: boolean
  emptyMessage?: string
  // Off by default (Production Plan already has its own Total
  // Revenue/Cost/Profit cards beside the table - see
  // ProductionAllocationPage.tsx - adding this footer there too would
  // duplicate them). Current Production Allocation's usage turns this
  // on, since it has no overall summary anywhere else.
  showFinancialSummary?: boolean
}

const UNAVAILABLE_AGGREGATE_MESSAGE =
  'One or more committed products has a required resource that is currently inactive or unpriced, so this total cannot be reliably calculated.'

// Same sign-before-₱ convention as Product Data Management's
// ProductTable.tsx::formatCurrency - kept as a local copy rather than
// a cross-module import, matching this codebase's existing convention
// of each page keeping its own small presentation helpers (see e.g.
// productionTypes.ts's ProductSummary comment).
const formatCurrency = (value: number) => {
  const magnitude = Math.abs(value).toLocaleString(undefined, {
    maximumFractionDigits: 2,
  })

  return value < 0 ? `-₱${magnitude}` : `₱${magnitude}`
}

const UNAVAILABLE_COST_MESSAGE =
  'Not available - a required resource for this product is currently inactive or has no price configured for this production cycle.'

const currencyCell = (value: number | null) =>
  value === null ? (
    <Tooltip label={UNAVAILABLE_COST_MESSAGE}>
      <span>—</span>
    </Tooltip>
  ) : (
    formatCurrency(value)
  )

const profitCell = (value: number | null) => {
  if (value === null) {
    return (
      <Tooltip label={UNAVAILABLE_COST_MESSAGE}>
        <span>—</span>
      </Tooltip>
    )
  }

  const color = value > 0 ? 'green' : value < 0 ? 'red' : 'gray'

  return (
    <Badge
      color={color}
      variant="light"
      size="sm"
      style={{ flexShrink: 0, whiteSpace: 'nowrap' }}
      styles={{
        label: {
          overflow: 'visible',
          textOverflow: 'clip',
          whiteSpace: 'nowrap',
        },
      }}
    >
      {formatCurrency(value)}
    </Badge>
  )
}

const ProductionPlanTable = ({
  plans,
  isLoading,
  isError,
  emptyMessage: emptyMessageOverride,
  showFinancialSummary = false,
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
    {
      accessor: 'totalCost',
      title: 'Total Cost',
      textAlign: 'right',
      render: (row) => currencyCell(row.totalCost),
    },
    {
      accessor: 'totalRevenue',
      title: 'Total Revenue',
      textAlign: 'right',
      render: (row) => formatCurrency(row.totalRevenue),
    },
    {
      accessor: 'totalProfit',
      title: 'Total Profit',
      textAlign: 'right',
      render: (row) => profitCell(row.totalProfit),
    },
  ]

  const totalQuantity = plans.reduce(
    (sum, item) => sum + item.quantity,
    0,
  )

  // Overall Revenue always sums cleanly (never null per-row). Overall
  // Cost/Profit fall back to "unavailable" as a whole - rather than
  // silently summing only the priced rows - the moment ANY row's cost
  // is unavailable, so the total never quietly understates what
  // production actually requires (same rule as the per-row values).
  const hasUnavailableCost = plans.some(
    (plan) => plan.totalCost === null,
  )

  const overallRevenue = plans.reduce(
    (sum, plan) => sum + plan.totalRevenue,
    0,
  )

  const overallCost = hasUnavailableCost
    ? null
    : plans.reduce((sum, plan) => sum + (plan.totalCost ?? 0), 0)

  const overallProfit = hasUnavailableCost
    ? null
    : plans.reduce((sum, plan) => sum + (plan.totalProfit ?? 0), 0)

  const emptyMessage = isLoading
    ? 'Loading...'
    : isError
      ? 'Unable to load the production plan.'
      : (emptyMessageOverride ??
        'No production plan generated yet. Click "Generate Optimal Production Plan" above.')

  return (
    <>
      <ScrollArea type="auto" offsetScrollbars>
        <AppTable
          columns={columns}
          data={isLoading ? [] : plans}
          emptyMessage={emptyMessage}
        />
      </ScrollArea>

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

      {showFinancialSummary && (
        <>
          <Group justify="space-between" mt="xs">
            <Text fw={500}>
              Overall Total Cost
            </Text>

            {overallCost === null ? (
              <Tooltip label={UNAVAILABLE_AGGREGATE_MESSAGE}>
                <Text fw={700}>—</Text>
              </Tooltip>
            ) : (
              <Text fw={700}>{formatCurrency(overallCost)}</Text>
            )}
          </Group>

          <Group justify="space-between" mt="xs">
            <Text fw={500}>
              Overall Total Revenue
            </Text>

            <Text fw={700}>
              {formatCurrency(overallRevenue)}
            </Text>
          </Group>

          <Group justify="space-between" mt="xs">
            <Text fw={500}>
              Overall Total Profit
            </Text>

            {overallProfit === null ? (
              <Tooltip label={UNAVAILABLE_AGGREGATE_MESSAGE}>
                <Text fw={700}>—</Text>
              </Tooltip>
            ) : (
              <Text fw={700}>{formatCurrency(overallProfit)}</Text>
            )}
          </Group>
        </>
      )}
    </>
  )
}

export default ProductionPlanTable

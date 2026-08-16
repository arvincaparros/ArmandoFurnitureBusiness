import { Badge, ScrollArea, Tooltip } from '@mantine/core'

import AppTable, {
  type Column,
} from '../../../components/tables/AppTable'

import type { Product } from '../types'
import type { ResourceOption } from '../api/productResourceTypes'

import ProductRowActions from './ProductRowActions'

import styles from './ProductTable.module.css'

interface ProductTableProps {
  products: Product[]
  // Currently-active resource catalog (['resources-all'], filtered)
  // - this, not any hardcoded list, is what decides which resource
  // columns exist at all. A resource gaining/losing a column is a
  // direct consequence of it entering/leaving this array.
  activeResources: ResourceOption[]
  onEdit: (product: Product) => void
  onDelete: (product: Product) => void

  isLoading: boolean
  isError: boolean

  sortBy: keyof Product | string
  reverse: boolean
  onSort: (
    accessor: keyof Product | string,
  ) => void
}

const COST_UNAVAILABLE_MESSAGE =
  'Not available - a resource this product requires has no price configured for the current production cycle yet (set it on the Resources page).'

// Sign goes before the ₱ symbol (e.g. "-₱2,680", not "₱-2,680") -
// only Profit can go negative among the columns using this
// formatter (Material/Labor/Machine/Total/Selling Price are always
// >= 0 by construction), so this only changes Profit's appearance.
const formatCurrency = (value: number) => {
  const magnitude = Math.abs(value).toLocaleString(undefined, {
    maximumFractionDigits: 2,
  })

  return value < 0 ? `-₱${magnitude}` : `₱${magnitude}`
}

// Cost/profit values are derived entirely from resource usage x
// CycleResource pricing (see productAdapter.ts::calculateCosts) -
// null means genuinely unknown (missing pricing for a required
// resource), never a fabricated or partial number, so it stays a
// dash with an explanation rather than a misleading 0 or ₱0.
const costCell = (value: number | null) =>
  value === null ? (
    <Tooltip label={COST_UNAVAILABLE_MESSAGE}>
      <span>—</span>
    </Tooltip>
  ) : (
    formatCurrency(value)
  )

// Same green/red financial-status convention already used elsewhere
// in this app (e.g. BottleneckAlert, RequirementRow's gray Badge) -
// color-codes the same calculated profit value/formatting as
// costCell, purely a presentational wrapper around it.
const profitCell = (value: number | null) => {
  if (value === null) {
    return (
      <Tooltip label={COST_UNAVAILABLE_MESSAGE}>
        <span>—</span>
      </Tooltip>
    )
  }

  const color = value > 0 ? 'green' : value < 0 ? 'red' : 'gray'

  return (
    // Mantine's Badge truncates its label with an ellipsis by
    // default (styles/Badge.css - width: fit-content combined with
    // overflow: hidden/text-overflow: ellipsis on both the root and
    // label), sized for short fixed chips - not appropriate for a
    // variable-length currency amount like "-₱10,668". Overriding
    // just the label's overflow behavior keeps the badge's shape/
    // colors untouched while letting it size to its full content;
    // flexShrink: 0 stops AppTable's flex Group wrapper (justify=
    // "flex-end" for right-aligned columns) from compressing it.
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

const NO_REQUIREMENT_RECORDED =
  'No requirement recorded for this resource on this product.'

// Resource columns are dynamic now (see below) - every column that
// exists corresponds to a real, currently-active resource by
// construction, so the only reason a cell is empty is that this
// specific product has no requirement for it. Real requirement data
// comes from GET /api/products/{id}/resources (the same endpoint and
// resolveRequirements() the Edit Product modal uses) - undefined here
// means genuinely no requirement, never a fabricated 0.
const resourceCell = (value: number | undefined) =>
  value === undefined ? (
    <Tooltip label={NO_REQUIREMENT_RECORDED}>
      <span>—</span>
    </Tooltip>
  ) : (
    value
  )

const ProductTable = ({
  products,
  activeResources,
  onEdit,
  onDelete,
  isLoading,
  isError,
  sortBy,
  reverse,
  onSort,
}: ProductTableProps) => {
  // One column per currently-active resource, matched to each
  // product's requirement by resource id (the canonical relationship
  // - never by resource name/string). No hardcoded resource list of
  // any kind: adding, renaming, or deactivating a resource changes
  // this array on the next fetch of the already-shared
  // ['resources-all'] query, which is exactly what regenerates these
  // columns without any code change or page refresh.
  const resourceColumns: Column<Product>[] = activeResources.map(
    (resource) => ({
      accessor: `resource-${resource.id}`,
      title: `${resource.name} (${resource.unit})`,
      textAlign: 'center',
      render: (row) =>
        resourceCell(row.resourceQuantities[resource.id]),
    }),
  )

  const columns: Column<Product>[] = [
    {
        accessor: 'productName',
        title: 'Furniture',
        sortable: true,
    },
    ...resourceColumns,
    {
        accessor: 'sellingPrice',
        title: 'Selling Price',
        sortable: true,
        textAlign: 'right',
        render: (row) =>
        `₱${row.sellingPrice.toLocaleString()}`,
    },
    {
        accessor: 'materialCost',
        title: 'Material',
        textAlign: 'right',
        render: (row) => costCell(row.materialCost),
    },
    {
        accessor: 'laborCost',
        title: 'Labor',
        textAlign: 'right',
        render: (row) => costCell(row.laborCost),
    },
    {
        accessor: 'machineCost',
        title: 'Machine',
        textAlign: 'right',
        render: (row) => costCell(row.machineCost),
    },
    {
        accessor: 'totalCost',
        title: 'Total',
        textAlign: 'right',
        render: (row) => costCell(row.totalCost),
    },
    {
        accessor: 'profit',
        title: 'Profit',
        // Content-sized badge (see profitCell), plus a minimum
        // column width so it always has room for the longest
        // realistic value (e.g. "-₱10,668") without relying on the
        // browser's auto table layout alone.
        width: 110,
        textAlign: 'right',
        render: (row) => profitCell(row.profit),
    },
    {
        accessor: 'actions',
        title: 'Actions',
        width: 90,
        textAlign: 'center',
        render: (row) => (
          <ProductRowActions
            product={row}
            onEdit={onEdit}
            onDelete={onDelete}
          />
        ),
    },
  ]

  const emptyMessage = isLoading
    ? 'Loading products...'
    : isError
      ? 'Unable to load products.'
      : 'No products found.'

  return (
    <ScrollArea
        type="auto"
        offsetScrollbars
        className={styles.stickyActionsScrollArea}
        // Fills ProductDataPage.module.css's .tableArea (flex: 1,
        // min-height: 0) so this becomes a real bounded scroll
        // region on desktop instead of growing to the table's full
        // content height - that growth was what pushed the whole
        // page taller than the viewport. ScrollArea's default
        // scrollbars="xy" already supports both axes; it just never
        // had a constrained height to actually need vertical scroll
        // before now. On mobile, .tableArea resets to normal flow
        // (display: block; flex: none), so this height: 100% simply
        // has no bounded ancestor to fill and has no effect there.
        style={{ height: '100%' }}
    >
        <AppTable
        columns={columns}
        data={isLoading ? [] : products}
        sortBy={sortBy}
        reverse={reverse}
        onSort={onSort}
        emptyMessage={emptyMessage}
        />
    </ScrollArea>
  )
}

export default ProductTable

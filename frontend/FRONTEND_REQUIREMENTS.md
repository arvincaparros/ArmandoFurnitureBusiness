# Frontend Requirements Audit

**Scope:** Read-only audit of `C:\Projects\ArmandoFurnitureBusiness\frontend`. This document describes exactly what the frontend code currently requires — components, actions, data fields, and expected response shapes — based solely on reading the frontend source. **No comparison against the backend was performed, and no backend changes are recommended here.** This file is the source of truth for "what the frontend needs" to be used in a later gap-analysis step.

Every field name below is copied verbatim from the frontend TypeScript source — nothing has been renamed or normalized.

---

## 1. Frontend Project Overview

| Item | Value |
|---|---|
| Project name | `frontend` (package.json `name: "frontend"`), part of the Armando Furniture Business system |
| Frontend framework | React 19 (`react@^19.2.8`, `react-dom@^19.2.8`) |
| Programming language | TypeScript (`typescript@~6.0.2`), `.tsx`/`.ts` throughout |
| Build tool | Vite 8 (`vite@^8.2.0`, `@vitejs/plugin-react`) |
| UI framework/library | Mantine v9 (`@mantine/core`, `@mantine/charts`, `@mantine/form`, `@mantine/hooks`, `@mantine/notifications`) + `@tabler/icons-react` + `lucide-react` icons; charts also use `recharts` directly in places |
| State management | Local component state only (`useState` in each page/hook). No global store (no Redux/Zustand/Context-based data store). `@tanstack/react-query@^5.101.4` is installed and `QueryClientProvider` is mounted app-wide (`src/app/providers.tsx`), but **no `useQuery`/`useMutation` call exists anywhere in the codebase today** — it is unused plumbing. |
| API client | `axios@^1.19.0` is installed but **not imported or used anywhere in `src/`**. No HTTP client, no fetch wrapper, no `.env` files, no Vite dev proxy configured. |
| Routing | `react-router-dom@^7.18.2`, `BrowserRouter` + `Routes`/`Route` in `src/app/router.tsx` |
| Main application entry point | `src/main.tsx` → `<Providers><App /></Providers>` → `src/App.tsx` → `AppRouter` (`src/app/router.tsx`) |
| Main frontend folder structure | `src/{app, assets, components, constants, hooks, layouts, pages, theme, utils}`; every business feature lives under `src/pages/<feature>/` with its own `{types.ts, mock/, hooks/use<Feature>.ts, components/, <Feature>Page.tsx}` |

### Cross-cutting observations (frontend-only facts, not backend gaps)

- **No API/service layer exists anywhere.** Every page's hook returns static arrays imported from a local `mock/*.ts` file. This is uniform across all 9 pages — there is no "reference implementation" page already talking to a real API.
- **Authentication is not implemented.** `src/pages/auth/LoginPage.tsx` is a two-line stub (`<h1>Login</h1>`) mounted at `/login`; nothing links to it, `AppLayout` renders `<Outlet/>` unconditionally with no guard, and the header's "Logout" menu item (`src/layouts/header/Header.tsx`) has no `onClick` handler. No token storage, no interceptors.
- **Two parallel, inconsistent navigation sources exist:**
  - `src/constants/navigation.ts` — 7 entries, used only by `src/hooks/useCurrentPage.ts` (which itself is imported nowhere in the app — dead code). Its paths are stale: it points Forecast at `/forecast` (actual route is `/demand-forecasting`) and has no entry at all for `/optimization-history`.
  - `src/layouts/sidebar/Sidebar.tsx` — 8 hardcoded menu entries, which match the live routes in `src/app/router.tsx` and are what the user actually navigates with.
- Several shared components exist as **empty stub files** (0 bytes): `src/components/common/Loading.tsx`, `src/components/common/EmptyState.tsx`, `src/components/feedback/ErrorView.tsx`, `src/components/feedback/LoadingView.tsx`, `src/components/feedback/NoDataView.tsx`, `src/components/tables/DataToolbar.tsx`, `src/components/tables/EmptyTable.tsx`, `src/components/charts/ForecastChart.tsx`, `src/pages/demand-forecasting/components/ForecastChatInput.tsx`, `src/pages/dashboard/hooks/useDashboard.ts`, `src/pages/production-allocation/components/EmptyState.tsx`. These are scaffolded but not implemented or used by any module.
- Shared generic building blocks actually in use: `PageHeader`, `ChartCard`, `StatCard` (cards), `AppTable` (generic sortable table with built-in empty-message support), `notify` (Mantine notifications wrapper for add/update/delete/save/export toasts), `exportCsv`/`exportExcel` (client-side file export utilities).

---

## 2. Discovered Frontend Modules

Discovered from `src/app/router.tsx` (routes) and `src/layouts/sidebar/Sidebar.tsx` (menu), cross-checked against `src/pages/*`:

| # | Module (as implemented) | Route | Exists? |
|---|---|---|---|
| 1 | Dashboard | `/dashboard` | ✅ |
| 2 | Resources Management | `/resources` | ✅ |
| 3 | Product Data Management | `/products` | ✅ (includes per-product resource/requirement fields inline — see note below) |
| 4 | Production Allocation | `/production` | ✅ (this is the "generate optimal plan" / optimization screen) |
| 5 | Resource Utilization Report | `/reports` | ✅ |
| 6 | Transaction History | `/history` | ✅ |
| 7 | Optimization History | `/optimization-history` | ✅ |
| 8 | Demand Forecasting | `/demand-forecasting` | ✅ (includes an embedded AI chatbot widget) |
| 9 | Auth / Login | `/login` | ⚠️ stub page only, no logic |

Checked against the requested checklist:
- **Product Resource Requirements** — no separate module/route/page exists. The concept is folded directly into **Product Data Management**: `Product` objects carry flat resource-quantity fields (`wood`, `epoxy`, `nails`, `glue`, `sandpaper`, `doorknob`) and machine/labor-hour fields (`laborHours`, `sawHours`, `thicknessPlanerHours`, `handPlanerHours`) on the same record as the product itself.
- **Production Cycles** — no such module, route, page, type, or component exists anywhere in `src/`.
- **Optimization** (as distinct from "Production Allocation" and "Optimization History") — no separate module exists. "Production Allocation" (`/production`) is the single-run optimizer screen; "Optimization History" (`/optimization-history`) is the historical log of past runs.
- **Forecast History** — no frontend module, page, route, component, type, or mock data exists for forecast history specifically. (Do not confuse with "Optimization History," which is a different, unrelated domain — production-optimization runs, not demand forecasts.)

No other business modules were found beyond the 8 listed above (plus the non-functional Auth stub).

---

## Module: Dashboard

### Purpose
Landing page giving an at-a-glance overview: KPI stat cards, a production-recommendations table, a resource-utilization donut/pie breakdown, and a row of quick-action shortcut buttons.

### Routes
- `/dashboard` → `src/pages/dashboard/DashboardPage.tsx`

### Main Components
- `DashboardStats.tsx` — renders `StatCard` grid from `dashboardStats`
- `DashboardRecommendations.tsx` — renders `AppTable` from `productionRecommendations`
- `DashboardResourceUtilization.tsx` — renders a `recharts` `PieChart` from `resourceUtilization`
- `DashboardQuickActions.tsx` — renders a static row of 5 buttons (labels only, **no `onClick` handlers wired** — purely decorative today)

### User Actions
- View only. No create/edit/delete/search/filter/sort actions exist on this page. Quick-action buttons render but do nothing (no handlers).

### Expected Output

| UI element | Component/file | What the user sees | Data required to render it |
|---|---|---|---|
| KPI stat cards (×4) | `DashboardStats.tsx` / `StatCard` | Total Available Resources, Expected Revenue, Expected Profit, Waste Percentage — each with icon, title, value, description | `DashboardStat[]` |
| Production Recommendations table | `DashboardRecommendations.tsx` | Table of furniture name, recommended quantity, expected profit | array of `{ id, name, quantity, profit }` |
| Resource Utilization pie chart | `DashboardResourceUtilization.tsx` | Donut/pie chart of resource categories by % share, with legend/tooltip | array of `{ name, value }` |
| Quick Actions row | `DashboardQuickActions.tsx` | 5 buttons: Manage Resources, Manage Products Data, Generate Product Plan, View Reports, View History | none (static labels, no data binding) |

### Required Data

| UI Element | Data Required | Field | Type | Required? | Used By |
|---|---|---|---|---|---|
| Stat card | Card id | `id` | string | Yes | `DashboardStat` |
| Stat card | Card title | `title` | string | Yes | `DashboardStat` |
| Stat card | Card value (pre-formatted) | `value` | string \| number | Yes | `DashboardStat` |
| Stat card | Description | `description` | string | No | `DashboardStat` |
| Stat card | Accent color | `color` | string | No | `DashboardStat` |
| Stat card | Icon | `icon` | `LucideIcon` | Yes | `DashboardStat` |
| Recommendations row | Furniture name | `name` | string | Yes | table row |
| Recommendations row | Recommended quantity (pre-formatted, e.g. "12 units") | `quantity` | string | Yes | table row |
| Recommendations row | Expected profit (pre-formatted, e.g. "₱36,000") | `profit` | string | Yes | table row |
| Utilization pie slice | Category name | `name` | string | Yes | `ResourceUsage` |
| Utilization pie slice | Share value | `value` | number | Yes | `ResourceUsage` |

Note: `dashboardStats.value`, `recommendations.quantity`, and `recommendations.profit` are consumed as **already-formatted display strings** in the mock (e.g. `'₱285,400'`, `'12 units'`), not raw numbers — the components do no formatting themselves for these fields.

Also present in `types.ts` but **not currently rendered by any component**: `ProductionTrend { month, production }` and `RecentActivity { id, activity, user, date }` — defined types with no consuming UI today.

### Request/Payload Requirements
None. Dashboard is read-only; no forms, no mutations.

### Expected API Response(s)

```json
// Stat cards
[
  {
    "id": "total-resources",
    "title": "Total Available Resources",
    "value": "1,248 units",
    "description": "Current inventory",
    "color": "blue"
  }
]

// Production recommendations
[
  { "id": 1, "name": "Dining Table (6-seater)", "quantity": "12 units", "profit": "₱36,000" }
]

// Resource utilization breakdown
[
  { "name": "Wood", "value": 33 }
]
```
(`icon` is a frontend-only field resolved from a local icon map / lucide component, not expected from an API.)

---

## Module: Resources Management

### Purpose
Full CRUD management of raw-material/resource inventory (e.g. wood, epoxy) with search and column sorting.

### Routes
- `/resources` → `src/pages/resources-management/ResourcesPage.tsx`

### Main Components
- `ResourceToolbar.tsx` — "Add Resource" + "Save Changes" buttons
- `ResourceTable.tsx` — sortable `AppTable`, per-row edit/delete via `ResourceRowActions.tsx`
- `AddResourceModal.tsx` — create/edit form (dual-purpose based on whether `resource` prop is passed)
- `DeleteResourceModal.tsx` — delete confirmation dialog showing resource summary

### User Actions
- **View** — table of all resources
- **Create** — "Add Resource" opens `AddResourceModal` with empty form
- **Edit** — row pencil icon opens `AddResourceModal` pre-filled
- **Delete** — row trash icon opens `DeleteResourceModal`, confirm deletes
- **Search** — free-text filter on `resourceType` (client-side, case-insensitive substring)
- **Sort** — click any sortable column header (`resourceType`, `availableQuantity`, `unitPrice`); toggles ascending/descending
- **Save** ("Save Changes" button) — currently only triggers a generic "saved" toast; no distinct payload

### Expected Output

| UI element | Component/file | What the user sees | Data required |
|---|---|---|---|
| Resource table | `ResourceTable.tsx` | Columns: Resource Type, Available Quantity, Unit Price (₱-formatted), Actions | `Resource[]` |
| Search box | `ResourcesPage.tsx` (inline `TextInput`) | Live-filters table by resource type | `Resource[]` (client-filtered) |
| Add/Edit modal | `AddResourceModal.tsx` | Form: Resource Type (text), Available Quantity (number), Unit (select: board ft/liter/kg/pcs/hrs/set), Unit Price (number, ₱-prefixed) | `Resource` (on edit) |
| Delete modal | `DeleteResourceModal.tsx` | Confirmation card showing resource type, qty+unit, unit price | `Resource` |

### Required Data

| UI Element | Data Required | Field | Type | Required? | Used By |
|---|---|---|---|---|---|
| Resource table | Row id | `id` | number | Yes | `Resource` |
| Resource table | Resource name | `resourceType` | string | Yes | `Resource`, `ResourceTable` |
| Resource table | Available quantity | `availableQuantity` | number | Yes | `Resource`, `ResourceTable` |
| Resource table | Unit | `unit` | string | Yes | `Resource`, `AddResourceModal` |
| Resource table | Unit price | `unitPrice` | number | Yes | `Resource`, `ResourceTable` (rendered as `₱{value.toFixed(2)}`) |

### Request/Payload Requirements
**Create/Update payload** (`onSave` callback in `AddResourceModal.tsx`), identical shape for both:
```ts
{
  id: number,              // Date.now() for new, existing id for edit
  resourceType: string,
  availableQuantity: number,
  unit: string,
  unitPrice: number,
}
```
Client-side validation before save is enabled: `resourceType` non-empty, `availableQuantity > 0`, `unitPrice > 0`.

**Delete**: only `id` (via the selected `Resource.id`) is needed to identify the target row; no request body beyond identifying the resource.

### Expected API Response Shape
```json
[
  {
    "id": 1,
    "resourceType": "Wood (board ft)",
    "availableQuantity": 1250,
    "unit": "board ft",
    "unitPrice": 84
  }
]
```

---

## Module: Product Data Management

### Purpose
Manage the furniture product catalog: each product's raw-material/resource usage, machine/labor hours, selling price, and computed cost/profit figures. This module is where "Product Resource Requirements" data lives — there is no separate module for it.

### Routes
- `/products` → `src/pages/product-data-management/ProductDataPage.tsx`

### Main Components
- `ProductToolbar.tsx` — "Add Product" + "Save Changes" buttons
- `ProductTable.tsx` — sortable `AppTable` (17 columns; **no Actions column wired** — see note)
- `AddProductModal.tsx` — create/edit form (dual-purpose)
- `DeleteProductModal.tsx` — delete confirmation modal
- `ProductRowActions.tsx` — edit/delete icon buttons component (**defined but not actually placed inside `ProductTable`'s column list — currently unreachable from the UI**)

### User Actions
- **View** — full product table
- **Create** — "Add Product" opens `AddProductModal`
- **Search** — free-text filter on `productName`
- **Sort** — click `productName`, `totalCost`, or `profit` column headers
- **Save** ("Save Changes" button) — generic "saved" toast only
- **Edit / Delete** — components (`ProductRowActions`, `DeleteProductModal`) exist and are imported into the page, but are **not functionally reachable**: `ProductTable` renders no Actions column, and `DeleteProductModal` is wired with `product={null}` and a no-op `onConfirm={() => {}}`. `useProducts.ts` does export `updateProduct`/`deleteProduct`, but the page never calls them.

### Expected Output

| UI element | Component/file | What the user sees | Data required |
|---|---|---|---|
| Product table | `ProductTable.tsx` | 17 columns: Furniture, Wood, Epoxy, Nails, Glue, Sandpaper, Doorknob, Labor Hrs, Saw Hrs, T. Planer, H. Planer, Selling Price (₱), Material (₱), Labor (₱), Machine (₱), Total (₱), Profit (₱, red if negative) | `Product[]` |
| Search box | `ProductDataPage.tsx` | Live-filters by product name | `Product[]` (client-filtered) |
| Add/Edit modal | `AddProductModal.tsx` | Sectioned form: Product Name + Selling Price, "Resource Usage" (Wood/Epoxy/Nails/Glue/Sandpaper/Doorknob), "Machine & Labor" (Saw/Labor/Thickness Planer/Hand Planer hours) | `Product` (on edit) |

### Required Data

| UI Element | Data Required | Field | Type | Required? | Used By |
|---|---|---|---|---|---|
| Product table | Row id | `id` | number | Yes | `Product` |
| Product table | Product name | `productName` | string | Yes | `Product` |
| Product table | Wood usage | `wood` | number | Yes | `Product` |
| Product table | Epoxy usage | `epoxy` | number | Yes | `Product` |
| Product table | Nails usage | `nails` | number | Yes | `Product` |
| Product table | Glue usage | `glue` | number | Yes | `Product` |
| Product table | Sandpaper usage | `sandpaper` | number | Yes | `Product` |
| Product table | Doorknob usage | `doorknob` | number | Yes | `Product` |
| Product table | Labor hours | `laborHours` | number | Yes | `Product` |
| Product table | Saw hours | `sawHours` | number | Yes | `Product` |
| Product table | Thickness planer hours | `thicknessPlanerHours` | number | Yes | `Product` |
| Product table | Hand planer hours | `handPlanerHours` | number | Yes | `Product` |
| Product table | Selling price | `sellingPrice` | number | Yes | `Product` |
| Product table | Material cost | `materialCost` | number | Yes | `Product` |
| Product table | Labor cost | `laborCost` | number | Yes | `Product` |
| Product table | Machine cost | `machineCost` | number | Yes | `Product` |
| Product table | Total cost | `totalCost` | number | Yes | `Product` |
| Product table | Profit | `profit` | number | Yes | `Product` |

### Request/Payload Requirements
**Create/Update payload** (`onSave` in `AddProductModal.tsx`):
```ts
{
  id: number,
  productName: string,
  wood: number, epoxy: number, nails: number, glue: number, sandpaper: number, doorknob: number,
  laborHours: number, sawHours: number, thicknessPlanerHours: number, handPlanerHours: number,
  sellingPrice: number,
  materialCost: number,   // frontend currently hardcodes this to 0 on save
  laborCost: number,      // hardcoded to 0 on save
  machineCost: number,    // hardcoded to 0 on save
  totalCost: number,      // computed client-side as materialCost+laborCost+machineCost (currently always 0)
  profit: number,         // computed client-side as sellingPrice - totalCost
}
```
Validation before save: `productName` non-empty, `sellingPrice > 0`.

**Important frontend-observed fact:** the Add/Edit form never lets the user set `materialCost`/`laborCost`/`machineCost` — the modal hardcodes them to `0` and derives `totalCost`/`profit` from that. The *mock* data (`productData.ts`), by contrast, ships with nonzero `laborCost`/`totalCost` values. This means the frontend's own create/edit flow does not currently know how to compute real costs — it expects those numbers to come from somewhere else (cost calculation is not implemented client-side beyond the placeholder).

### Expected API Response Shape
```json
[
  {
    "id": 1,
    "productName": "Dining Table (4 seat)",
    "wood": 40, "epoxy": 2, "nails": 50, "glue": 1, "sandpaper": 3, "doorknob": 0,
    "laborHours": 20, "sawHours": 1, "thicknessPlanerHours": 0.5, "handPlanerHours": 1,
    "sellingPrice": 18000,
    "materialCost": 0, "laborCost": 1800, "machineCost": 0, "totalCost": 1800, "profit": 16200
  }
]
```

---

## Module: Production Allocation

### Purpose
Single-run production optimizer: generates a recommended production plan (which products, what quantities) to maximize profit, and shows the resulting financial summary and run metadata.

### Routes
- `/production` → `src/pages/production-allocation/ProductionAllocationPage.tsx`

### Main Components
- `GeneratePlanButton.tsx` — "Generate Optimal Production Plan" button
- `ProductionPlanTable.tsx` — table of planned products+quantities, with computed totals footer
- `SummaryCards.tsx` — Total Revenue / Total Cost / Total Profit cards
- `OptimizationInfoCard.tsx` — Start / End / Duration of the optimization run
- `EmptyState.tsx` — **empty stub file, unused**

### User Actions
- **Generate** — "Generate Optimal Production Plan" button calls `generatePlan()`, which currently only does `console.log('Generate Production Plan')` — no state change, no request.
- View only otherwise (no search/sort/filter/edit/delete on this page).

### Expected Output

| UI element | Component/file | What the user sees | Data required |
|---|---|---|---|
| Production plan table | `ProductionPlanTable.tsx` | Furniture Type, Quantity to Produce, plus footer totals (Total Furniture Types, Total Quantity — computed client-side from the row list) | `ProductionPlan[]` |
| Summary cards | `SummaryCards.tsx` | Total Revenue, Total Cost, Total Profit (each ₱-formatted) | `OptimizationSummary` |
| Optimization info card | `OptimizationInfoCard.tsx` | Start time, End time, Duration | `OptimizationSummary` |

### Required Data

| UI Element | Data Required | Field | Type | Required? | Used By |
|---|---|---|---|---|---|
| Plan table row | Row id | `id` | number | Yes | `ProductionPlan` |
| Plan table row | Product name | `productName` | string | Yes | `ProductionPlan` |
| Plan table row | Quantity to produce | `quantity` | number | Yes | `ProductionPlan` |
| Summary card | Total revenue | `totalRevenue` | number | Yes | `OptimizationSummary` |
| Summary card | Total cost | `totalCost` | number | Yes | `OptimizationSummary` |
| Summary card | Total profit | `totalProfit` | number | Yes | `OptimizationSummary` |
| Info card | Run start time | `startTime` | string (pre-formatted, e.g. `"5:42:18 PM"`) | Yes | `OptimizationSummary` |
| Info card | Run end time | `endTime` | string (pre-formatted) | Yes | `OptimizationSummary` |
| Info card | Run duration | `duration` | string (pre-formatted, e.g. `"808 ms"`) | Yes | `OptimizationSummary` |

### Request/Payload Requirements
"Generate" action currently takes no parameters and sends no request — `generatePlan()` is a no-op. The frontend defines no input form for constraints (e.g. no way to select which products/resources to include) — whatever request shape backs "generate" is not yet expressed anywhere in the frontend code.

### Expected API Response Shape
```json
{
  "plans": [
    { "id": 1, "productName": "Dining Table", "quantity": 12 }
  ],
  "summary": {
    "totalRevenue": 285400,
    "totalCost": 188680,
    "totalProfit": 96720,
    "startTime": "5:42:18 PM",
    "endTime": "5:42:18 PM",
    "duration": "808 ms"
  }
}
```
(Frontend keeps `plans` and `summary` as two separate values returned from the hook; whether the future API bundles them in one response or two is not determined by the frontend today.)

---

## Module: Resource Utilization Report

### Purpose
Read-only analytics view of how heavily each resource was consumed by the last optimization/production run, plus a bottleneck-analysis callout.

### Routes
- `/reports` → `src/pages/resource-utilization-report/ResourceUtilizationReportPage.tsx`

### Main Components
- `SummaryCards.tsx` — 4 top-level KPI cards
- `UtilizationTable.tsx` — per-resource consumption table with progress bars
- `UtilizationProgress.tsx` — colored progress bar + percentage label (red ≥90%, yellow ≥70%, else green)
- `UtilizationPieChart.tsx` — `DonutChart` (Mantine charts) of category breakdown + legend
- `BottleneckAlert.tsx` — red alert box listing bottlenecked resources with reason + recommendation

### User Actions
View only. No create/edit/delete/search/sort/filter/export actions exist on this page.

### Expected Output

| UI element | Component/file | What the user sees | Data required |
|---|---|---|---|
| Summary cards (×4) | `SummaryCards.tsx` | Overall Utilization Rate (%), Total Raw Materials Consumed (units), Total Labor Hours Used (used/capacity), Total Machine Hours Used (used/capacity) | `UtilizationSummary` |
| Utilization table | `UtilizationTable.tsx` | Resource, Total Consumed, Total Remaining, Overall Utilization % (progress bar + label), Utilization Visual (colored progress bar) | `UtilizationResource[]` |
| Pie/donut chart | `UtilizationPieChart.tsx` | Category share (Raw Materials / Labor / Machine Hours) as % with colored legend swatches | `PieChartData[]` |
| Bottleneck alert | `BottleneckAlert.tsx` | List of resource, reason, and recommendation per bottleneck | `Bottleneck[]` |

### Required Data

| UI Element | Data Required | Field | Type | Required? | Used By |
|---|---|---|---|---|---|
| Summary card | Utilization rate | `utilizationRate` | number | Yes | `UtilizationSummary` |
| Summary card | Total raw materials consumed | `totalRawMaterials` | number | Yes | `UtilizationSummary` |
| Summary card | Labor used | `laborUsed` | number | Yes | `UtilizationSummary` |
| Summary card | Labor capacity | `laborCapacity` | number | Yes | `UtilizationSummary` |
| Summary card | Machine used | `machineUsed` | number | Yes | `UtilizationSummary` |
| Summary card | Machine capacity | `machineCapacity` | number | Yes | `UtilizationSummary` |
| Utilization table row | Row id | `id` | number | Yes | `UtilizationResource` |
| Utilization table row | Resource name | `resourceName` | string | Yes | `UtilizationResource` |
| Utilization table row | Total consumed | `totalConsumed` | number | Yes | `UtilizationResource` |
| Utilization table row | Total remaining | `totalRemaining` | number | Yes | `UtilizationResource` |
| Utilization table row | Utilization % | `utilizationPercent` | number | Yes | `UtilizationResource` |
| Pie chart segment | Category name | `name` | string | Yes | `PieChartData` |
| Pie chart segment | Value (%) | `value` | number | Yes | `PieChartData` |
| Pie chart segment | Color (Mantine color token) | `color` | string | Yes | `PieChartData` |
| Bottleneck item | Row id | `id` | number | Yes | `Bottleneck` |
| Bottleneck item | Resource name | `resource` | string | Yes | `Bottleneck` |
| Bottleneck item | Reason text | `reason` | string | Yes | `Bottleneck` |
| Bottleneck item | Recommendation text | `recommendation` | string | Yes | `Bottleneck` |

### Request/Payload Requirements
None — read-only page, no forms or mutations. (Note: `pieChartData` is imported directly from the mock module in `ResourceUtilizationReportPage.tsx` rather than being destructured from `useResourceUtilization()`, unlike `summary`/`resources`/`bottlenecks` — a frontend wiring quirk worth knowing when replacing the mock, since the pie chart's data source bypasses the hook entirely today.)

### Expected API Response Shape
```json
{
  "summary": {
    "utilizationRate": 81.4,
    "totalRawMaterials": 2150,
    "laborUsed": 480, "laborCapacity": 576,
    "machineUsed": 310, "machineCapacity": 672
  },
  "resources": [
    { "id": 1, "resourceName": "Wood (board ft)", "totalConsumed": 478, "totalRemaining": 22, "utilizationPercent": 95.6 }
  ],
  "pieChartData": [
    { "name": "Raw Materials", "value": 55, "color": "brown.8" }
  ],
  "bottlenecks": [
    { "id": 1, "resource": "Wood (board ft)", "reason": "Inventory level reached usable capacity.", "recommendation": "Increase wood stock." }
  ]
}
```

---

## Module: Transaction History

### Purpose
Log of actual production + sales transactions (as opposed to forecasted/planned figures), with create, search, sort, and CSV/Excel export.

### Routes
- `/history` → `src/pages/transaction-history/TransactionHistoryPage.tsx`

### Main Components
- `TransactionToolbar.tsx` — "Add Transaction" button + Export dropdown (CSV / Excel)
- `TransactionTable.tsx` — sortable `AppTable`, 8 columns
- `AddTransactionModal.tsx` — create form (supports edit via optional `transaction` prop, though the page currently only invokes it in "add" mode)

### User Actions
- **View** — full transaction table
- **Create** — "Add Transaction" opens `AddTransactionModal`
- **Search** — free-text filter across `transactionNumber` OR `furnitureProduct`
- **Sort** — click any sortable column header (all 8 columns are sortable)
- **Export CSV** — downloads current filtered/sorted rows as `.csv` (client-side generated)
- **Export Excel** — downloads current filtered/sorted rows as `.xlsx` (via `exceljs`, client-side generated)
- Edit/Delete: `useTransactions.ts` exposes `updateTransaction`/`deleteTransaction`, but no UI in this page currently calls them (no edit/delete buttons wired in `TransactionTable`).

### Expected Output

| UI element | Component/file | What the user sees | Data required |
|---|---|---|---|
| Transaction table | `TransactionTable.tsx` | Transaction #, Date, Furniture Product, Quantity Produced, Sold, Sales (₱), Production Cost (₱), Profit Earned (₱, green if ≥0 else red) | `Transaction[]` |
| Search box | `TransactionHistoryPage.tsx` | Live-filters by transaction number or product name | `Transaction[]` (client-filtered) |
| Add modal | `AddTransactionModal.tsx` | Transaction Number, Date (date picker), Furniture Product (searchable select from a fixed 9-item list), Quantity Produced, Quantity Sold, Sales Amount, Production Cost, and a **read-only** computed Profit Earned field | none (auto-generates transaction number + today's date as defaults) |
| Export | `TransactionToolbar.tsx` | Menu: "Export as CSV" / "Export as Excel" | `Transaction[]` (currently filtered/sorted set) |

### Required Data

| UI Element | Data Required | Field | Type | Required? | Used By |
|---|---|---|---|---|---|
| Transaction table | Row id | `id` | number | Yes | `Transaction` |
| Transaction table | Transaction number | `transactionNumber` | string | Yes | `Transaction` |
| Transaction table | Date | `date` | string (ISO `YYYY-MM-DD`) | Yes | `Transaction` |
| Transaction table | Product name | `furnitureProduct` | string | Yes | `Transaction` |
| Transaction table | Quantity produced | `quantityProduced` | number | Yes | `Transaction` |
| Transaction table | Quantity sold | `quantitySold` | number | Yes | `Transaction` |
| Transaction table | Sales amount | `salesAmount` | number | Yes | `Transaction` |
| Transaction table | Production cost | `productionCost` | number | Yes | `Transaction` |
| Transaction table | Profit earned | `profitEarned` | number | Yes | `Transaction` |

### Request/Payload Requirements
**Create/Update payload** (`onSave` in `AddTransactionModal.tsx`):
```ts
{
  id: number,                 // Date.now() for new
  transactionNumber: string,  // client auto-generates `TRX-${Date.now()}` as a default
  date: string,                // YYYY-MM-DD, defaults to today
  furnitureProduct: string,    // chosen from a hardcoded 9-option list (not fetched)
  quantityProduced: number,
  quantitySold: number,
  salesAmount: number,
  productionCost: number,
  profitEarned: number,        // computed client-side as salesAmount - productionCost
}
```
No client-side required-field validation is enforced on this form (unlike Resources/Products, the Save button here has no `isValid`/`disabled` gate).

The `furnitureProduct` select is currently a **hardcoded string list** in `AddTransactionModal.tsx` (`productOptions`), not sourced from the Product Data Management module's product list — worth noting since a real integration would likely need this to be dynamic.

### Expected API Response Shape
```json
[
  {
    "id": 1,
    "transactionNumber": "TRX-1001",
    "date": "2026-06-06",
    "furnitureProduct": "Dining Table (6-seater)",
    "quantityProduced": 5,
    "quantitySold": 4,
    "salesAmount": 120000,
    "productionCost": 80000,
    "profitEarned": 40000
  }
]
```

---

## Module: Optimization History

### Purpose
Historical log of past production-optimization runs (id, timestamp, duration, financial results), plus a line chart of profit trend across runs. This is a distinct domain from Demand Forecasting.

### Routes
- `/optimization-history` → `src/pages/optimization-history/OptimizationHistoryPage.tsx`

### Main Components
- `OptimizationToolbar.tsx` — "Run Manual Optimization" button
- `OptimizationHistoryTable.tsx` — table of past runs
- `OptimizationHistoryChart.tsx` — Mantine `LineChart` of profit per run

### User Actions
- **Run** — "Run Manual Optimization" button calls a handler that currently only `console.log('Run manual optimization')` — no request, no state change, no query invalidation (this page doesn't even use a mutation-like pattern from its hook).
- View only otherwise — no search/sort/filter/create/edit/delete on this page.

### Expected Output

| UI element | Component/file | What the user sees | Data required |
|---|---|---|---|
| History table | `OptimizationHistoryTable.tsx` | Optimization ID, Date Generated, Duration (ms), Total Profit (₱), Total Production Cost (₱), Products Produced | `OptimizationHistory[]` |
| Profit trend chart | `OptimizationHistoryChart.tsx` | Line chart of profit (₱) per optimization run, x-axis = optimization ID | `ProfitTrend[]` |

### Required Data

| UI Element | Data Required | Field | Type | Required? | Used By |
|---|---|---|---|---|---|
| History table row | Row id | `id` | number | Yes | `OptimizationHistory` |
| History table row | Optimization run id | `optimizationId` | string | Yes | `OptimizationHistory` |
| History table row | Timestamp generated | `dateGenerated` | string | Yes | `OptimizationHistory` |
| History table row | Run duration | `duration` | number (ms) | Yes | `OptimizationHistory` |
| History table row | Total profit | `totalProfit` | number | Yes | `OptimizationHistory` |
| History table row | Total production cost | `totalProductionCost` | number | Yes | `OptimizationHistory` |
| History table row | Products produced count | `productsProduced` | number | Yes | `OptimizationHistory` |
| Chart point | Run id (x-axis) | `optimizationId` | string | Yes | `ProfitTrend` |
| Chart point | Profit (y-axis) | `profit` | number | Yes | `ProfitTrend` |

### Request/Payload Requirements
"Run Manual Optimization" currently takes no parameters and sends no request — it is a no-op `console.log`. No input form exists for this action.

### Expected API Response Shape
```json
{
  "history": [
    {
      "id": 1,
      "optimizationId": "OP-220",
      "dateGenerated": "2026-06-06 08:16:02",
      "duration": 812,
      "totalProfit": 96720,
      "totalProductionCost": 188680,
      "productsProduced": 57
    }
  ],
  "profitTrend": [
    { "optimizationId": "OP-215", "profit": 77500 }
  ]
}
```
(Frontend hook returns `optimizationHistory` and `profitTrendData` as two separate arrays; note `profitTrendData` appears to be a derived/reshaped view of the same runs in `optimizationHistory`, just sorted ascending and with fewer fields — the frontend does not compute this derivation itself, it's baked into the separate mock array.)

---

## Module: Demand Forecasting

### Purpose
AI-assisted demand forecast dashboard: a per-product forecast table, a historical-vs-forecasted demand line chart, and an embedded chat assistant panel. (Already covered in depth in the prior inspection; restated here for completeness of this requirements doc.)

### Routes
- `/demand-forecasting` → `src/pages/demand-forecasting/DemandForecastingPage.tsx`

### Main Components
- `ForecastToolbar.tsx` — "Run Demand Optimization" button
- `ForecastTable.tsx` — forecast-per-product table
- `ForecastChart.tsx` (page-local) — Mantine `LineChart`, historical vs. forecasted demand
- `ForecastChatbot.tsx` — chat panel (message list + input); `ForecastChatInput.tsx` is an empty/unused file
- `src/components/charts/ForecastChart.tsx` (shared/generic version) — **empty file, unused**

### User Actions
- **Run** — "Run Demand Optimization" calls `runForecast()`, currently `console.log('Running demand forecast...')` only — no state change.
- **Open/close chat** — toggles the chatbot panel (desktop floating button + mobile bottom-sheet variant).
- **Send chat message** — appends to local input state and `console.log`s the message; not persisted, not connected to any backend, and does not append to the displayed `messages` list.
- No search/filter/sort/export/select-product actions exist on this page today.

### Expected Output

| UI element | Component/file | What the user sees | Data required |
|---|---|---|---|
| Forecast table | `ForecastTable.tsx` | Furniture Product, Historical Sales (Units), Predicted Demand (Units), Forecast Period, Confidence Level (%), Forecast Status (green check icon if `'success'`, else raw text) | `ForecastItem[]` |
| Forecast chart | `ForecastChart.tsx` | Line chart with two series: Historical Demand (solid) and Forecasted Demand (dashed), y-axis fixed 0–360, tooltip shows "N units" | `ForecastChartData[]` |
| Chat panel | `ForecastChatbot.tsx` | Scrollable message bubbles (right-aligned for user, left for assistant) + text input + send button | `ChatMessage[]` |

### Required Data

| UI Element | Data Required | Field | Type | Required? | Used By |
|---|---|---|---|---|---|
| Forecast table | Product name | `furnitureProduct` | string | Yes | `ForecastItem` |
| Forecast table | Historical sales | `historicalSales` | number | Yes | `ForecastItem` |
| Forecast table | Predicted demand | `predictedDemand` | number | Yes | `ForecastItem` |
| Forecast table | Forecast period | `forecastPeriod` | string | Yes | `ForecastItem` |
| Forecast table | Confidence level | `confidenceLevel` | number | Yes | `ForecastItem` (rendered as `{value.toFixed(1)}%`) |
| Forecast table | Status | `status` | `'success' \| 'pending' \| 'failed'` | Yes | `ForecastItem` |
| Forecast chart | Month label (x-axis) | `month` | string | Yes | `ForecastChartData` |
| Forecast chart | Historical demand (y) | `historicalDemand` | number | No (optional) | `ForecastChartData` |
| Forecast chart | Forecasted demand (y) | `forecastedDemand` | number | No (optional) | `ForecastChartData` |
| Chat message | Message id | `id` | number | Yes | `ChatMessage` |
| Chat message | Sender role | `role` | `'user' \| 'assistant'` | Yes | `ChatMessage` |
| Chat message | Message text | `message` | string | Yes | `ChatMessage` |

Note: `ForecastItem` has **no `id` or `product_id`-equivalent field today** — rows are keyed only by array index in the table render, and the table is keyed on `furnitureProduct` name, not a numeric id (though the type does declare `id: number`, it isn't used as a React key by `ForecastTable`/`AppTable`, which key on array `index`).

### Request/Payload Requirements
"Run Demand Optimization" currently takes no parameters and sends no request. No product-selection control exists to scope the forecast/chart to a single product — chart and table currently always show the full mock set.

### Expected API Response Shape
```json
// Forecast table rows
[
  {
    "id": 1,
    "furnitureProduct": "Dining Table (6-seater)",
    "historicalSales": 280,
    "predictedDemand": 315,
    "forecastPeriod": "Jul 2026",
    "confidenceLevel": 91.2,
    "status": "success"
  }
]

// Chart series (wide/pivoted, one row per month)
[
  { "month": "Jan '26", "historicalDemand": 55 },
  { "month": "May '26", "historicalDemand": 220, "forecastedDemand": 220 },
  { "month": "Aug '26", "forecastedDemand": 315 }
]

// Chat messages
[
  { "id": 1, "role": "assistant", "message": "Hello, Admin! ..." }
]
```

---

## Module: Auth (stub — not a functional module)

### Purpose
Placeholder route only. No login logic, no session/token handling, no logout action anywhere in the frontend.

### Routes
- `/login` → `src/pages/auth/LoginPage.tsx` (renders only `<h1>Login</h1>`)

### Main Components
None beyond the stub itself.

### User Actions
None implemented. (Header has a "Logout" menu item with no handler; no "Login" form fields, buttons, or validation exist.)

### Expected Output / Required Data / Request Payload / API Response
Not applicable — there is no implementation to derive requirements from. Explicitly out of scope per this audit's instructions (do not invent auth requirements).

---

## Summary: modules with functioning create/update/delete vs. read-only vs. stubbed actions

| Module | Create | Edit | Delete | Search | Sort | Export | "Generate/Run" action wired to real logic? |
|---|---|---|---|---|---|---|---|
| Dashboard | – | – | – | – | – | – | n/a |
| Resources Management | ✅ | ✅ | ✅ | ✅ | ✅ | – | n/a |
| Product Data Management | ✅ | ⚠️ built but unreachable | ⚠️ built but unreachable | ✅ | ✅ | – | n/a |
| Production Allocation | – | – | – | – | – | – | ❌ no-op (`console.log`) |
| Resource Utilization Report | – | – | – | – | – | – | n/a |
| Transaction History | ✅ | ⚠️ hook supports it, no UI | ⚠️ hook supports it, no UI | ✅ | ✅ | ✅ (CSV/Excel) | n/a |
| Optimization History | – | – | – | – | – | – | ❌ no-op (`console.log`) |
| Demand Forecasting | – | – | – | – | – | – | ❌ no-op (`console.log`) |

This table is itself a frontend fact (not a recommendation) — it shows exactly which "Run/Generate" buttons are currently decorative versus which CRUD flows are fully working against local mock state.

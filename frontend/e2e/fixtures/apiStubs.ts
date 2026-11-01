import type { Page } from '@playwright/test'

// Every /api/** call is fulfilled here. Nothing in this suite reaches
// a real backend, so no database - development or test - is involved
// at any point. That is what makes these specs safe to run under the
// plan's Global Constraints, and it is why the stubs have to cover
// every endpoint the pages touch rather than only the interesting
// ones: an unstubbed route would otherwise fall through to the real
// API host.

export interface OpeningInventoryItemStub {
  id: number
  product_id: number
  quantity: string
  notes: string | null
}

export interface OpeningInventorySetStub {
  id: number
  set_number: string
  status: string
  effective_date: string
  notes: string | null
  created_at: string
  reviewed_at: string | null
  created_by_username: string | null
  reviewed_by_username: string | null
  items: OpeningInventoryItemStub[]
}

export interface StubOverrides {
  openingStatus?: {
    stock_validation_enabled: boolean
    reviewed_set: OpeningInventorySetStub | null
    draft_set: OpeningInventorySetStub | null
  }
  inventory?: Record<string, unknown>
  transactions?: Record<string, unknown>
  applications?: Record<string, unknown>[]
  history?: Record<string, unknown>[]
}

// POST bodies the specs assert against. Returned by installApiStubs so
// a spec can check what the UI actually SENT, not merely what it
// showed - that is the only way to prove, e.g., that
// quantity_produced is absent from the create payload.
export interface RecordedRequests {
  transactionCalls: Record<string, unknown>[]
  reviewCalls: number[]
  applyCalls: string[]
}

const CYCLE_ID = 3

const PRODUCT = {
  id: 1,
  name: 'Ordinary Table',
  selling_price: '2500.00',
  labor_cost: '0.00',
  is_active: true,
  minimum_demand: '0.0000',
}

const LATEST_CYCLE = {
  id: CYCLE_ID,
  cycle_date: '2026-10-25T00:00:00',
  start_date: '2026-10-25T00:00:00',
  end_date: '2026-11-01T00:00:00',
  status: 'OPEN',
}

const DEFAULT_INVENTORY = {
  cycle_id: CYCLE_ID,
  cycle_start_date: '2026-10-25T00:00:00',
  cycle_end_date: '2026-11-01T00:00:00',
  stock_validation_enabled: true,
  products: [
    {
      product_id: 1,
      product_name: 'Ordinary Table',
      opening_quantity: '4.0000',
      total_produced: '20.0000',
      total_sold: '9.0000',
      available_stock: '15.0000',
      cycle_produced: '20.0000',
      cycle_sold: '9.0000',
    },
  ],
}

const DEFAULT_OPENING_STATUS = {
  stock_validation_enabled: true,
  reviewed_set: null,
  draft_set: null,
}

const DEFAULT_TRANSACTIONS = {
  items: [],
  total: 0,
  range: null,
  available: null,
}

// One OPTIMAL run with a per-product result, so the Production
// Allocation page resolves a latest optimal plan and can enable Apply.
const DEFAULT_HISTORY = [
  {
    id: 7,
    production_cycle_id: CYCLE_ID,
    started_at: '2026-10-30T09:00:00',
    completed_at: '2026-10-30T09:00:01',
    duration_ms: 1000,
    status: 'OPTIMAL',
    objective_value: '25000.0000',
    total_profit: '25000.0000',
    total_cost: '0.0000',
    total_revenue: '25000.0000',
    products_produced: 10,
    is_summary_only: false,
    is_hidden: false,
    results: [
      {
        product_id: 1,
        recommended_quantity: '10.0000',
        unit_profit: '2500.0000',
        total_profit: '25000.0000',
      },
    ],
  },
]

const json = (body: unknown) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(body),
})

export async function installApiStubs(
  page: Page,
  overrides: StubOverrides = {},
): Promise<RecordedRequests> {
  const recorded: RecordedRequests = {
    transactionCalls: [],
    reviewCalls: [],
    applyCalls: [],
  }

  const openingStatus =
    overrides.openingStatus ?? DEFAULT_OPENING_STATUS
  const inventory = overrides.inventory ?? DEFAULT_INVENTORY
  const transactions =
    overrides.transactions ?? DEFAULT_TRANSACTIONS
  const applications = overrides.applications ?? []
  const history = overrides.history ?? DEFAULT_HISTORY

  // ProtectedRoute only renders once a token is present AND
  // /api/auth/me resolves - seed the token with the real key from
  // src/api/tokenStorage.ts before any script runs.
  await page.addInitScript(() => {
    window.localStorage.setItem(
      'armando_access_token',
      'e2e-stub-token',
    )
  })

  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    // CRITICAL: the '**/api/**' glob also matches Vite's own module
    // scripts, because the app's source lives at /src/api/*.ts. Those
    // must reach the dev server untouched - fulfilling them as JSON
    // breaks the module graph and the page renders nothing at all.
    // Only a pathname rooted at /api/ is a real backend call.
    if (!path.startsWith('/api/')) {
      return route.fallback()
    }

    if (method === 'POST' || method === 'PATCH') {
      if (path === '/api/transactions') {
        recorded.transactionCalls.push(
          request.postDataJSON() as Record<string, unknown>,
        )

        return route.fulfill(
          json({
            id: 1,
            transaction_number: 'TRX-000001',
            product_id: 1,
            production_cycle_id: CYCLE_ID,
            transaction_date: '2026-10-31T00:00:00',
            quantity_produced: '20.0000',
            quantity: '1.0000',
            unit_price: '2500.00',
            total_sales: '2500.00',
            production_cost: '0.00',
            unit_profit: '2500.0000',
            total_profit: '2500.0000',
          }),
        )
      }

      if (/\/api\/opening-inventory\/\d+\/review$/.test(path)) {
        const id = Number(path.split('/')[3])

        recorded.reviewCalls.push(id)

        return route.fulfill(
          json({
            ...(openingStatus.draft_set ?? {}),
            status: 'REVIEWED',
            reviewed_at: '2026-10-31T00:00:00',
            reviewed_by_username: 'arvin',
          }),
        )
      }

      if (path.endsWith('/optimize/apply')) {
        recorded.applyCalls.push(path)

        return route.fulfill(
          json({
            cycle_id: CYCLE_ID,
            status: 'OPTIMAL',
            objective: 'MAX_PROFIT',
            total_revenue: '25000.00',
            total_cost: '0.00',
            total_profit: '25000.00',
            allocations: [],
            resource_usage: [],
            bottlenecks: [],
          }),
        )
      }

      if (path === '/api/auth/login') {
        return route.fulfill(
          json({
            access_token: 'e2e-stub-token',
            token_type: 'bearer',
          }),
        )
      }

      return route.fulfill(json({}))
    }

    // ---- GET routes -------------------------------------------
    if (path === '/api/auth/me') {
      return route.fulfill(
        json({
          id: 1,
          username: 'arvin',
          email: 'arvin@example.com',
          is_active: true,
        }),
      )
    }

    if (path === '/api/products') {
      return route.fulfill(json([PRODUCT]))
    }

    if (path === '/api/production-cycles/latest') {
      return route.fulfill(json(LATEST_CYCLE))
    }

    if (path === '/api/inventory') {
      return route.fulfill(json(inventory))
    }

    if (path === '/api/opening-inventory/active') {
      return route.fulfill(json(openingStatus))
    }

    if (path === '/api/opening-inventory') {
      const sets = [
        openingStatus.reviewed_set,
        openingStatus.draft_set,
      ].filter(Boolean)

      return route.fulfill(json(sets))
    }

    if (path === '/api/transactions') {
      return route.fulfill(json(transactions))
    }

    if (path === '/api/optimization/history') {
      return route.fulfill(json(history))
    }

    if (/\/api\/production-cycles\/\d+\/applications$/.test(path)) {
      return route.fulfill(json(applications))
    }

    if (/\/api\/production-cycles\/\d+\/allocations$/.test(path)) {
      return route.fulfill(json([]))
    }

    if (/\/api\/production-cycles\/\d+\/feasibility$/.test(path)) {
      return route.fulfill(
        json({
          cycle_id: CYCLE_ID,
          is_feasible: true,
          resources: [],
          bottlenecks: [],
          needs_reoptimization: false,
          applied_at: null,
        }),
      )
    }

    if (/\/api\/production-cycles\/\d+\/resources$/.test(path)) {
      return route.fulfill(json([]))
    }

    if (path === '/api/forecast') {
      return route.fulfill(
        json({ forecast_period: 'NEXT_CYCLE', products: [] }),
      )
    }

    if (path.startsWith('/api/forecast')) {
      return route.fulfill(json({ products: [] }))
    }

    // Anything the pages ask for that this suite does not care about
    // still has to be fulfilled locally rather than reaching a real
    // host - an empty array is the safe shape for every list endpoint
    // left.
    return route.fulfill(json([]))
  })

  return recorded
}

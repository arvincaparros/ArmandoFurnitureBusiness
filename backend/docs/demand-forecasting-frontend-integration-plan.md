# Demand Forecasting — Frontend Integration Implementation Plan

**Status:** Planning document only. No code, config, or migrations have been changed to produce this plan.
**Sources:** `frontend/FRONTEND_REQUIREMENTS.md` and the Demand Forecasting frontend↔backend comparison produced in this session (backend contract independently re-verified against `app/routers/forecast.py`, `app/schemas/forecast.py`, `app/services/forecasting.py`, `app/services/forecast_history.py`, `app/database/models.py`, and migration `c4cebd8094aa`).

---

## 1. Purpose & Scope

Wire the Demand Forecasting page (`/demand-forecasting`) to the real backend (`/api/forecast/*`), and add the Forecast History module the frontend currently lacks entirely. This plan sequences the work, calls out every place a straight pass-through won't work, and flags the decisions that need a product/design call before implementation starts.

**Out of scope:** the chat assistant (§9), authentication (none exists on these routes today, matching current frontend behavior), and any backend changes — the backend contract is treated as fixed and correct for this plan.

---

## 2. Status Quo

| Area | Current state |
|---|---|
| API client | `axios` is installed but imported nowhere in `src/`. No fetch wrapper, no `.env`, no Vite dev proxy. |
| Data fetching | `@tanstack/react-query` is installed and `QueryClientProvider` is mounted app-wide, but no `useQuery`/`useMutation` exists anywhere yet — unused plumbing. |
| Demand Forecasting page | `useForecast.ts` returns static arrays from `mock/forecastData.ts`. "Run Demand Optimization" is a `console.log` no-op. Chat sends nothing anywhere. |
| Forecast History | No module, route, page, component, type, or mock data exists. |
| Test tooling | No test runner (`vitest`/`jest`) is present in `package.json` today. |

---

## 3. Source-of-Truth Rule

Per the backend contract (§19), the backend is authoritative for forecast values, confidence, status, trend, and forecast periods. **The frontend must only render and adapt what the API returns — never recompute forecasts, confidence, status, or periods client-side.** Every task below is a rendering/adaptation task, not a calculation task.

---

## 4. Architecture Additions Needed

These are prerequisites shared by every phase below.

### 4.1 API client
Stand up a thin `axios` instance (already a dependency — no new package needed) with a configurable base URL, e.g. `src/api/client.ts`. Base URL should come from a Vite env var (`VITE_API_BASE_URL`), since no `.env` file exists yet — one needs to be introduced (`.env.development` pointing at the local backend, `.env.example` committed for other developers).

**Decision needed:** dev-time CORS/proxy strategy — either the backend enables CORS for the Vite dev origin, or `vite.config.ts` gets a `server.proxy` entry for `/api`. Either works; pick one so `VITE_API_BASE_URL` doesn't have to differ between dev and prod.

### 4.2 Data fetching
Adopt `@tanstack/react-query` for this module rather than reaching for a new pattern — it's already installed and provider-mounted, just unused. Each GET endpoint becomes a `useQuery`; `POST /api/forecast/generate` becomes a `useMutation` that invalidates the forecast + history queries on success (so the table refreshes and the new run appears in history without a manual refetch).

### 4.3 Decimal parsing utility
Every quantity/confidence field on every forecast endpoint is a JSON **string** (Decimal serialization — contract §14), with precision that varies by source (`"0"` vs `"12.0000"`). Add one small shared parser, e.g. `parseDecimal(value: string | null): number | null`, and route every Decimal field through it. Do not `parseFloat` ad hoc at each call site — centralizing this is what makes the precision-variance behavior documented in the contract a non-issue.

### 4.4 Adapter layer, not a type rewrite
Recommendation: keep the frontend's existing UI-facing types (`ForecastItem`, `ForecastChartData`) largely as they are — they're reasonable view models — and introduce an explicit **mapper module** (e.g. `src/pages/demand-forecasting/adapters/`) that translates the backend's wire shape into them. This isolates every naming/type/vocabulary gap identified in the comparison to one reviewable place instead of scattering `snake_case`-to-`camelCase` and string-to-number conversions across components.

---

## 5. Phase 1 — Live Forecast Table (`GET /api/forecast`)

Replace `useForecast.ts`'s mock import with a `useQuery` against `GET /api/forecast`, then map `ForecastResponse.products[]` → `ForecastItem[]` through the adapter.

| Frontend field | Source | Adapter work required |
|---|---|---|
| `id` | `product_id` | Direct assign (also start using it as the table's real React key instead of array index — see §11). |
| `furnitureProduct` | `product_name` | Direct assign. |
| `historicalSales` | `historical_sales` | `parseDecimal()`. |
| `predictedDemand` | `predicted_demand` | `parseDecimal()`. |
| `confidenceLevel` | `confidence_level` | `parseDecimal()`. |
| `status` | `forecast_status` | **Needs a mapping function**, not a direct assign — see §11.1, backend values (`READY`/`LOW_CONFIDENCE`/`NO_DATA`) share no values with the frontend's current `'success'|'pending'|'failed'` enum. |
| `forecastPeriod` | *no direct backend equivalent on this endpoint* | **Needs a design decision** — see §11.2. |
| *(new)* `trend` | `trend` | Not in `ForecastItem` today — add the field and a table column (§11.3). |

**Loading/empty/error states:** wire the existing (currently empty) stub components — `src/components/feedback/LoadingView.tsx`, `ErrorView.tsx`, `NoDataView.tsx` — rather than building new ones. This is the first module that would actually implement them.

---

## 6. Phase 2 — Generate Forecast Action (`POST /api/forecast/generate`)

Replace `runForecast()`'s `console.log` with a `useMutation` calling `POST /api/forecast/generate` (bodiless — send no payload, matching both sides of the current contract). On success:
- Invalidate/refetch the Phase 1 forecast query so the table reflects the freshly persisted run.
- Invalidate the Phase 4 history query (§8) so the new run appears there too, if the user is on that page.
- Surface the existing `notify` toast helper (already used elsewhere for save/export) for success/failure feedback — no new notification pattern needed.

No request-body design work is required — this is the one place frontend and backend already agree exactly (comparison report, §"Request comparison").

---

## 7. Phase 3 — Forecast Chart (`GET /api/forecast/timeseries`)

This is the highest-effort phase because the shapes are structurally different, not just field-renamed.

**The gap:** the frontend's `ForecastChartData` is a flat array, one row per month, where a single row can carry both `historicalDemand` and `forecastedDemand`. The backend returns a nested, per-product structure (`products[].series[]`), where each point is either a historical point or the forecast point — never both — and different products can have different, non-aligned month ranges.

**Recommended approach:**
1. Add a **product selector** to the Demand Forecasting page (none exists today — this is a genuinely new UI element, not a hidden one). Aggregating multiple products' unit counts into one line is not meaningful (a chair and a dining table don't share a demand scale), so the chart should be scoped to one product at a time, the same way `?product_id=` is designed to be used.
2. Call `GET /api/forecast/timeseries?product_id=<selected>` and adapt the single returned product's `series[]` into `ForecastChartData[]` by mapping each point:
   - `is_forecast: false` → `{ month: period, historicalDemand: parseDecimal(historical_sales) }`
   - `is_forecast: true` (always exactly one, always last) → `{ month: period, forecastedDemand: parseDecimal(predicted_demand) }`
3. Default the selector to the first product returned by the Phase 1 forecast query on initial load (mirrors the "always show something" behavior of today's mock).
4. Drop or re-derive the chart's hardcoded `yAxisProps.domain: [0, 360]` — that range was sized for the mock dataset and will clip real values. Either compute the domain from the fetched series or let Mantine auto-scale.

**Decision needed:** should switching products refetch (`?product_id=`) or should the page fetch the unfiltered `GET /api/forecast/timeseries` once (all active products) and filter client-side? Fetching once is fewer round-trips if the product list is small and the selector is switched often; per-product fetching scales better if the product catalog grows. Either is compatible with the contract — flagging for a call based on expected catalog size.

---

## 8. Phase 4 — Forecast History Module (new)

Per the comparison, the frontend has no forecast-history module at all, while the backend has three fully tested endpoints (`/history`, `/history/latest`, `/history/{run_id}`). The closest existing analog in this codebase is **Optimization History** (`src/pages/optimization-history/`) — same shape of problem (a list of past runs plus a trend chart) — and is the recommended structural template: `OptimizationHistoryPage.tsx` → `OptimizationHistoryTable.tsx` + `OptimizationHistoryChart.tsx` + a toolbar, each with their own `types.ts` and `hooks/use*.ts`.

**Proposed structure:** `src/pages/forecast-history/` with `ForecastHistoryPage.tsx`, `components/ForecastHistoryTable.tsx`, `components/ForecastHistoryChart.tsx` (e.g. confidence or predicted-demand trend across runs, mirroring `OptimizationHistoryChart`'s profit-trend line), `hooks/useForecastHistory.ts`, `types.ts`.

| Requirement | Source | Notes |
|---|---|---|
| Run list | `GET /api/forecast/history` | Already ordered newest-first by the backend — no client-side sort needed for default view. |
| Run id, timestamp | `id`, `created_at` | `created_at` is ISO 8601 — format for display with the existing date-formatting convention used elsewhere (e.g. Transaction History's date column). |
| Per-product qty | `historical_quantity`, `forecast_quantity` | **Different field names than the live endpoint** — do not reuse the Phase 1 adapter as-is; this needs its own mapper reading the *unrenamed* field names (contract §15/§18). |
| Confidence, status | `confidence_level`, `forecast_status` | **Nullable here** (legacy pre-migration runs). Render a fallback (e.g. "—") when null — do not assume presence the way Phase 1 can. |
| Product name | *not returned by history endpoints* | History only has `product_id`. Resolve names via a one-time `GET /api/products` lookup (already consumed elsewhere in the app for Product Data Management) built into an `id → name` map, joined client-side. |

**Route & nav:** add `/forecast-history` to `router.tsx` and to `Sidebar.tsx` (the file that actually drives live navigation, per the frontend audit — `constants/navigation.ts` is confirmed dead code and should not be extended). Whether to also fix `constants/navigation.ts`'s stale entries while touching this area, or leave that cleanup for a separate pass, is a minor scoping call for whoever implements this phase.

**Single-run views** (`/history/latest`, `/history/{run_id}`) can back a "view run detail" drill-down from the history table if wanted, or be deferred — the list endpoint alone is enough for an MVP history page. Flagged as scope choice in §10.

---

## 9. Phase 5 (Deferred) — Chat Assistant

No chat/AI endpoint exists anywhere in the backend (confirmed: only six routes are registered under `forecast_router` in `main.py`). The frontend's `ForecastChatbot.tsx` is built but functionally inert (messages aren't even appended locally). This is **not a wiring task** — it requires a product decision on whether an AI backend is in scope at all, and if so, what it should answer (e.g. Q&A over the forecast data already being fetched, vs. a general assistant). Recommend leaving the chat UI as-is until that's decided; nothing in Phases 1–4 depends on it.

---

## 10. Open Decisions Requiring Product/Design Input

| # | Decision | Why it can't be resolved by engineering alone |
|---|---|---|
| 1 | How to display `forecast_status` (`READY`/`LOW_CONFIDENCE`/`NO_DATA`) — new icon per state, or collapse to the existing checkmark-or-text pattern? | Visual/UX call — `LOW_CONFIDENCE` arguably deserves its own treatment (e.g. a warning tone), not just "not success." |
| 2 | What to show in the table's "Forecast Period" column, given the live endpoint only returns the literal `"NEXT_CYCLE"` | Three options identified: (a) drop the column, (b) show the literal as-is, (c) join in each product's per-point `period` from an unfiltered `/timeseries` call fetched alongside `/api/forecast` (no extra backend work — one additional call already returns all active products at once). Recommend (c) for information value, but it's a scope/cost tradeoff worth a product call. |
| 3 | Chart data-fetch strategy: fetch-once-and-filter vs. refetch-per-product-selection (§7) | Depends on expected product catalog size, not resolvable from current code alone. |
| 4 | History drill-down: is a per-run detail view needed at launch, or is the list sufficient? | Product scoping call, not a technical constraint. |
| 5 | Chat assistant scope (§9) | Entirely undecided; no backend surface exists to design against yet. |

---

## 11. UI/Type Changes Summary

### 11.1 `status` field
Backend vocabulary (`READY`/`LOW_CONFIDENCE`/`NO_DATA`) has zero overlap with the frontend's current type (`'success'|'pending'|'failed'`). Recommend replacing the frontend `ForecastItem.status` type with the backend's own vocabulary and updating `ForecastTable.tsx`'s render logic to branch on it directly, rather than inventing a mapping to the old three-value enum — the old enum was never derived from a real backend and has no reason to be preserved. Exact per-status visual treatment is Decision #1 above.

### 11.2 `forecastPeriod` field
Cannot be populated from `GET /api/forecast` alone (contract-confirmed hardcoded literal). Resolution depends on Decision #2.

### 11.3 New `trend` field
Add `trend: 'INCREASING' | 'DECREASING' | 'STABLE' | 'NO_DATA'` to `ForecastItem` and a corresponding table column — the backend computes this on every forecast call today and it's currently discarded. Straightforward addition, not blocked on any decision.

---

## 12. Error Handling & Edge Cases to Implement

| Case | Backend behavior | Frontend handling needed |
|---|---|---|
| No forecast run ever generated, viewing `/forecast-history/latest`-backed UI | `404 {"detail": "No forecast history found"}` | Render `NoDataView` / an empty-state prompt to run a forecast, not a generic error. |
| Unknown or inactive `product_id` on `/timeseries` | `404 {"detail": "Product not found"}` | Product selector (§7) should only ever offer active product IDs already known from Phase 1's response, so this should be unreachable via normal UI use — still worth a defensive `ErrorView` fallback. |
| Product with zero sales history | `200`, `historical_sales`/`predicted_demand` = `"0"`, `trend: "NO_DATA"`, `forecast_status: "NO_DATA"` | Not an error — render normally; the adapter's `parseDecimal("0")` must not be treated as falsy/missing. |
| Legacy history run missing `confidence_level`/`forecast_status` | `200`, nulls | Table must render a fallback, not crash on `null.toFixed(...)`-style calls (the current mock-driven `ForecastTable.tsx` doesn't guard against null today). |
| Unhandled server error on any endpoint | Generic `500`, undocumented shape | Standard React Query error boundary / `ErrorView`, no endpoint-specific handling possible since the backend doesn't model this. |

---

## 13. Testing & Verification Plan

No test runner currently exists in `frontend/package.json` (no `vitest`/`jest`). Two tracks:

1. **Prerequisite (if unit/integration tests are wanted for this work):** introduce `vitest` + `@testing-library/react` before or alongside Phase 1 — there is no existing frontend test convention to follow yet, so this is a net-new decision, not a gap in this plan.
2. **Manual verification (available immediately, no new tooling):** for each phase, exercise the page against a running backend with (a) a product with rich sales history, (b) a zero-history product, and (c) — for Phase 4 — at least one pre-migration-style history run with null `confidence_level`/`forecast_status` if a way to simulate that is available, to confirm the null-fallback rendering actually works and doesn't throw.

---

## 14. Recommended Sequencing

```
1. API client + Decimal parser + adapter scaffolding   (§4)
2. Phase 1 — live forecast table                         (§5)
3. Phase 2 — generate action                              (§6)   ← depends on Phase 1's query for invalidation
4. Phase 3 — chart                                        (§7)   ← independent of 2/4, can parallelize
5. Phase 4 — forecast history module                      (§8)   ← independent, can parallelize with 3
6. Phase 5 — chat                                         (§9)   ← blocked on product decision, not scheduled
```

Phases 3 and 4 have no dependency on each other and can be built in parallel once the Phase 1 scaffolding (API client, Decimal parser) lands.

---

## 15. Non-Goals

- No backend changes of any kind (endpoints, schemas, migrations) are proposed or required by this plan — every gap identified is resolvable entirely on the frontend.
- No authentication is introduced, matching the current (documented, intentional) unauthenticated state of these six endpoints.
- No change to how confidence/status/trend/period are *calculated* — the frontend only renders backend-provided values (§3).

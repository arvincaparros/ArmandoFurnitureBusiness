# Demand Forecasting + Inventory Ledger Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge `feat/production-inventory-ledger` into `main`, resolving the 5 conflicting Demand Forecasting files so that `main`'s weekly-bucket forecast architecture and the ledger's production-sourcing/stock-tracking feature both survive intact and correct.

**Architecture:** Keep `main`'s weekly-bucket/3-week-forecast shape as the outer structure of the timeseries endpoint. Split the historical layer into two independent, week-keyed series — sold (unchanged from `main`, minus the stale `quantity_produced` field) and produced (new, sourced from the ledger's `production_application_items` for post-rollout activity, falling back to the legacy `SalesTransaction.quantity_produced` column only for pre-rollout rows that have no ledger entry at all). Merge both series onto one chronological per-product point list via a `point_type` discriminator (`SALE` / `PRODUCTION` / `FORECAST`), exactly as the ledger branch already does at monthly granularity, just now at week granularity and summed within each week instead of one point per event.

**Tech Stack:** FastAPI + SQLAlchemy (backend), Pydantic schemas, React + TypeScript + Mantine Charts (frontend), pytest, vitest.

**Spec:** This plan's own "Proposed integration architecture" and "Conflict resolution strategy" sections below serve as the spec — there is no separate upstream design doc; the design was derived directly from independently diffing both branches against their merge base (`24f0b90`).

## Global Constraints

- Preserve `main`'s weekly-bucket historical aggregation and 3-week iterative forecast (`calculate_weekly_forecast`, `WEEKLY_FORECAST_WEEKS = 3`) exactly as-is — the forecast math itself is never touched by this integration.
- Never source a post-rollout sale's produced figure from `SalesTransaction.quantity_produced` — only from `production_application_items`.
- A pre-rollout sale (`production_cycle_id IS NULL`) has no ledger row; its own stored `quantity_produced` remains its only produced figure and must keep counting.
- Sales and production must stay visually and structurally distinguishable in both the API response (`point_type`) and the chart (a dedicated "Applied Production" series, not folded into the sales tooltip).
- No new Alembic migration is required by this integration — `main` added zero schema changes since the fork; the ledger branch's 3 migrations are already applied to both `armando_furniture` and `armando_furniture_test`.
- Do not touch `GET /api/forecast` (the monthly summary endpoint) or `get_monthly_historical_demand`/`calculate_forecast` — neither branch changed them, and this integration doesn't need to either.

---

## Proposed integration architecture

Today, two incompatible shapes compete for the same functions in `backend/app/services/forecasting.py`:

- `main`: one point per **week**, each point carrying both `historical_sales` (sold) and `quantity_produced` (summed straight from `SalesTransaction.quantity_produced` — now stale for any post-rollout sale), feeding a 3-week linear-trend forecast.
- `feat/production-inventory-ledger`: one point per **event** (one sale transaction, or one applied production batch), each `point_type`-tagged, merged onto a single-trailing-forecast-point monthly timeline. Production is correctly ledger-sourced, but the granularity and forecast horizon are unchanged from the pre-weekly design.

The combined design keeps `main`'s week-bucketed/3-week-forecast shape as the skeleton, and replaces only the *production* half of its data layer with a ledger-backed equivalent:

```
get_weekly_historical_demand(db)   -- UNCHANGED shape, trimmed: sold only (main)
get_weekly_produced_demand(db)     -- NEW: ledger-sourced + legacy-fallback, same week-bucket shape
calculate_weekly_forecast(...)     -- UNCHANGED (already reads only "quantity"/sold)
get_forecast_timeseries(db, ...)   -- REWRITTEN: merges the two series into one point list per product,
                                       point_type-tagged (SALE / PRODUCTION / FORECAST), production sorts
                                       before same-week sales, exactly 3 trailing FORECAST points anchored
                                       after the later of the two series' last week.
```

A week's **production** total is the sum of:
1. `production_application_items.quantity_produced` for every `ProductionApplication` whose `applied_at` falls in that week, plus
2. the stored `SalesTransaction.quantity_produced` of any sale in that week with `production_cycle_id IS NULL` (pre-rollout — it has no ledger row, so its own figure is all there is).

Per-event identity (`transaction_id`, `transaction_number`, `application_id`, `application_number`, `production_cycle_id`) does not survive week-level aggregation on *either* side of this merge — `main` already dropped `transaction_id`/`transaction_number` when it moved to weekly buckets, for the same reason. The combined point schema drops the ledger's three identity fields too, rather than keeping fields that are meaningless once more than one event can land in the same bucket. This is a deliberate simplification versus the ledger branch's monthly design, not an oversight.

A `SALE` point never carries `quantity_produced` in the combined design (that figure now lives exclusively on the matching `PRODUCTION` point for that week) — this removes the ledger's `None`-for-post-rollout special case entirely, because there's no longer a shared field to null out.

---

## File-by-file implementation plan

### Task 1: Backend schema — combined `ForecastTimeSeriesPoint` / `ProductTimeSeries`

**Files:**
- Modify: `backend/app/schemas/forecast.py:50-72` (the two classes both branches touched)
- Test: `backend/tests/test_forecast.py`, `backend/tests/test_forecast_weekly.py` (schema is exercised indirectly via the router tests — no dedicated schema unit test file exists today)

**Interfaces:**
- Produces: `ForecastTimeSeriesPoint(period: str, point_type: str, historical_sales: Decimal|None, quantity_produced: Decimal|None, predicted_demand: Decimal|None, is_forecast: bool)` and `ProductTimeSeries(product_id: int, product_name: str, trend: str, confidence_level: Decimal, series: list[ForecastTimeSeriesPoint])` — consumed by Task 2's `get_forecast_timeseries`.

- [ ] **Step 1: Replace the two classes**

```python
class ForecastTimeSeriesPoint(BaseModel):
    # point_type is the authoritative kind discriminator:
    #   SALE       - one calendar week's sold total (zero-filled).
    #                historical_sales carries the quantity SOLD.
    #                quantity_produced is always None here - produced
    #                figures live on the matching PRODUCTION point for
    #                the same week, never duplicated onto this one.
    #   PRODUCTION - one calendar week's produced total, summed from
    #                every production application applied that week,
    #                plus any pre-rollout (production_cycle_id IS NULL)
    #                sale's own stored quantity_produced for that week
    #                - its only production record, since it predates
    #                the ledger. Never zero-filled: a week with no
    #                production has no PRODUCTION point at all.
    #   FORECAST   - one of the three trailing weekly projections.
    # is_forecast is kept, unchanged, for every existing consumer: it
    # is True exactly when point_type == "FORECAST".
    period: str
    point_type: str
    historical_sales: Decimal | None = None
    quantity_produced: Decimal | None = None
    predicted_demand: Decimal | None = None
    is_forecast: bool


class ProductTimeSeries(BaseModel):
    product_id: int
    product_name: str
    # Computed once from the product's weekly SOLD series and shared
    # by every forecast point in `series` below - never recomputed
    # per point.
    trend: str
    confidence_level: Decimal
    series: list[ForecastTimeSeriesPoint]
```

- [ ] **Step 2: Run the existing forecast test files to confirm nothing outside this schema's own shape broke yet**

Run: `cd backend && python -m pytest tests/test_forecast.py tests/test_forecast_weekly.py -q`
Expected: FAIL at this point — `get_weekly_historical_demand`/`get_forecast_timeseries` in Task 2 haven't been updated yet, so callers passing the old field names will error. This is expected; Task 2 fixes it.

- [ ] **Step 3: Commit (staged together with Task 2 - schema and service must land in the same commit, since the schema change alone doesn't type-check against the old service code)**

Do not commit yet - continue directly to Task 2.

---

### Task 2: Backend service — weekly sold/produced split + rewritten timeseries builder

**Files:**
- Modify: `backend/app/services/forecasting.py` (replace `get_weekly_historical_demand`'s return shape; add `get_weekly_produced_demand`; rewrite `get_forecast_timeseries`)
- Test: `backend/tests/test_forecast_weekly.py`, new tests added in Task 3

**Interfaces:**
- Consumes: `ProductionApplication`, `ProductionApplicationItem` models (`app.database.models`), `_week_start`/`_next_week` (already in this file, unchanged).
- Produces: `get_weekly_historical_demand(db) -> dict[int, list[{"period": str, "quantity": Decimal}]]`, `get_weekly_produced_demand(db) -> dict[int, list[{"period": str, "quantity_produced": Decimal}]]`, `get_forecast_timeseries(db, product_id=None) -> dict` (consumed by `app/routers/forecast.py::get_timeseries`, unchanged caller).

- [ ] **Step 1: Trim `get_weekly_historical_demand` to sold-only**

Replace the function body (keep `_week_start`/`_next_week` calls identical; only the per-week dict shape and the SELECT's columns change):

```python
def get_weekly_historical_demand(
    db: Session,
) -> dict[int, list[dict]]:
    """
    Aggregate qualifying sales transactions into a chronological,
    zero-filled WEEKLY (Monday-start) SOLD series per active product.

    Produced figures are NOT part of this series - see
    get_weekly_produced_demand() for why quantity_produced is no
    longer summed from SalesTransaction here: that column is stale
    for any post-rollout sale, whose real production lives in the
    ledger instead.

    Qualification matches get_monthly_historical_demand() exactly
    (active product, quantity > 0).

    Returns, per product_id, a list of {"period": "YYYY-MM-DD",
    "quantity": Decimal} covering every calendar week (by its Monday
    start date) from that product's first to last qualifying
    transaction week, in ascending order, with weeks that have no
    qualifying transactions filled in as zero.
    """

    statement = (
        select(
            SalesTransaction.product_id,
            SalesTransaction.transaction_date,
            SalesTransaction.quantity,
        )
        .join(
            Product,
            Product.id == SalesTransaction.product_id,
        )
        .where(
            Product.is_active.is_(True),
            SalesTransaction.quantity > 0,
        )
        .order_by(
            SalesTransaction.product_id,
            SalesTransaction.transaction_date,
        )
    )

    rows = db.execute(statement).all()

    weekly_totals: dict[int, dict[date, Decimal]] = defaultdict(dict)

    for row in rows:
        week_key = _week_start(row.transaction_date)

        weekly_totals[row.product_id][week_key] = (
            weekly_totals[row.product_id].get(
                week_key, Decimal("0"),
            )
            + row.quantity
        )

    weekly_series: dict[int, list[dict]] = {}

    for product_id, totals_by_week in weekly_totals.items():
        weeks = sorted(totals_by_week.keys())
        week = weeks[0]
        last_week = weeks[-1]
        series = []

        while week <= last_week:
            series.append(
                {
                    "period": week.strftime("%Y-%m-%d"),
                    "quantity": totals_by_week.get(
                        week, Decimal("0"),
                    ),
                }
            )
            week = _next_week(week)

        weekly_series[product_id] = series

    return weekly_series
```

- [ ] **Step 2: Add `get_weekly_produced_demand`**

Add the required model imports at the top of the file (`from app.database.models import Product, ProductionApplication, ProductionApplicationItem, SalesTransaction`), then:

```python
def get_weekly_produced_demand(
    db: Session,
) -> dict[int, list[dict]]:
    """
    Aggregate production into a chronological, WEEKLY (Monday-start)
    PRODUCED series per active product - the production counterpart
    of get_weekly_historical_demand(), sourced from two places:

    1. production_application_items, grouped by the week its parent
       ProductionApplication was applied (applied_at) - the
       authoritative source for any production recorded after the
       ledger began. Mirrors forecasting's pre-ledger design note:
       never ProductionAllocation (a replaced-on-every-apply plan),
       never SalesTransaction.quantity_produced for these rows.
    2. SalesTransaction.quantity_produced, but ONLY for pre-rollout
       rows (production_cycle_id IS NULL) - rows with no ledger entry
       at all, for which this stored figure is the only production
       record that exists. A post-rollout sale's quantity_produced is
       never read here; its production is already counted via (1).

    NEVER zero-filled, unlike the sold series: a week with no
    production simply has no entry, so the chart shows no production
    point for it rather than a fabricated zero. Returns, per
    product_id, a list of {"period": "YYYY-MM-DD",
    "quantity_produced": Decimal}, ascending by period.
    """

    application_rows = db.execute(
        select(
            ProductionApplicationItem.product_id,
            ProductionApplicationItem.quantity_produced,
            ProductionApplication.applied_at,
        )
        .join(
            ProductionApplication,
            ProductionApplication.id
            == ProductionApplicationItem.production_application_id,
        )
        .join(
            Product,
            Product.id == ProductionApplicationItem.product_id,
        )
        .where(
            Product.is_active.is_(True),
            ProductionApplicationItem.quantity_produced > 0,
        )
    ).all()

    legacy_rows = db.execute(
        select(
            SalesTransaction.product_id,
            SalesTransaction.transaction_date,
            SalesTransaction.quantity_produced,
        )
        .join(
            Product,
            Product.id == SalesTransaction.product_id,
        )
        .where(
            Product.is_active.is_(True),
            SalesTransaction.production_cycle_id.is_(None),
            SalesTransaction.quantity_produced > 0,
        )
    ).all()

    weekly_totals: dict[int, dict[date, Decimal]] = defaultdict(dict)

    for row in application_rows:
        week_key = _week_start(row.applied_at)

        weekly_totals[row.product_id][week_key] = (
            weekly_totals[row.product_id].get(
                week_key, Decimal("0"),
            )
            + row.quantity_produced
        )

    for row in legacy_rows:
        week_key = _week_start(row.transaction_date)

        weekly_totals[row.product_id][week_key] = (
            weekly_totals[row.product_id].get(
                week_key, Decimal("0"),
            )
            + row.quantity_produced
        )

    return {
        product_id: [
            {
                "period": week.strftime("%Y-%m-%d"),
                "quantity_produced": quantity,
            }
            for week, quantity in sorted(totals_by_week.items())
        ]
        for product_id, totals_by_week in weekly_totals.items()
    }
```

- [ ] **Step 3: Rewrite `get_forecast_timeseries` to merge both series**

Replace the function body from `weekly_historical_demand = get_weekly_historical_demand(db)` onward:

```python
POINT_TYPE_SALE = "SALE"
POINT_TYPE_PRODUCTION = "PRODUCTION"
POINT_TYPE_FORECAST = "FORECAST"

# Production sorts before a same-week sale: the units have to exist
# before they can be sold, and a fixed tie-break keeps the x-axis
# order identical across requests.
_POINT_TYPE_SORT_RANK = {
    POINT_TYPE_PRODUCTION: 0,
    POINT_TYPE_SALE: 1,
}


def get_forecast_timeseries(
    db: Session,
    product_id: int | None = None,
) -> dict:
    """
    Build a weekly series per product merging two independent
    sources onto one chronological axis: one SALE point per calendar
    week of qualifying sold quantity (get_weekly_historical_demand(),
    zero-filled across the product's own first-to-last sold week) and
    one PRODUCTION point per calendar week with any produced quantity
    (get_weekly_produced_demand(), sparse - never zero-filled),
    followed by exactly WEEKLY_FORECAST_WEEKS trailing FORECAST
    points (calculate_weekly_forecast(), sales-only input, unchanged).

    Sales are authoritative for quantity SOLD, the ledger (plus the
    pre-rollout fallback) is authoritative for quantity PRODUCED, and
    neither is ever derived from the other - a week can have a SALE
    point with no PRODUCTION point, a PRODUCTION point with no SALE
    point, both, or neither.

    Forecast week 1 starts the week immediately after the LATER of
    the two series' own last week (so a product produced more
    recently than it last sold still anchors the forecast after that
    production, not stranded mid-series); weeks 2 and 3 follow
    consecutively. A product with no sold history at all still gets a
    forecast, anchored the week after today, exactly as before this
    change.
    """

    weekly_sold = get_weekly_historical_demand(db)
    weekly_produced = get_weekly_produced_demand(db)
    forecasts = calculate_weekly_forecast(weekly_sold)

    products_statement = (
        select(Product)
        .where(Product.is_active.is_(True))
    )

    if product_id is not None:
        products_statement = products_statement.where(
            Product.id == product_id
        )

    products = list(db.scalars(products_statement).all())

    today_week_start = _week_start(date.today())

    product_series = []

    for product in products:
        sold_weeks = weekly_sold.get(product.id, [])
        produced_weeks = weekly_produced.get(product.id, [])

        forecast = forecasts.get(
            product.id,
            {
                "forecast_quantities": [
                    Decimal("0")
                ] * WEEKLY_FORECAST_WEEKS,
                "trend": "NO_DATA",
                "confidence_level": Decimal("0.00"),
            },
        )

        points = [
            {
                "period": item["period"],
                "point_type": POINT_TYPE_SALE,
                "historical_sales": item["quantity"],
                "quantity_produced": None,
                "predicted_demand": None,
                "is_forecast": False,
            }
            for item in sold_weeks
        ] + [
            {
                "period": item["period"],
                "point_type": POINT_TYPE_PRODUCTION,
                "historical_sales": None,
                "quantity_produced": item["quantity_produced"],
                "predicted_demand": None,
                "is_forecast": False,
            }
            for item in produced_weeks
        ]

        points.sort(
            key=lambda point: (
                point["period"],
                _POINT_TYPE_SORT_RANK[point["point_type"]],
            )
        )

        last_week = (
            date.fromisoformat(points[-1]["period"])
            if points
            else today_week_start
        )

        week = _next_week(last_week)

        for forecast_quantity in forecast["forecast_quantities"]:
            points.append(
                {
                    "period": week.strftime("%Y-%m-%d"),
                    "point_type": POINT_TYPE_FORECAST,
                    "historical_sales": None,
                    "quantity_produced": None,
                    "predicted_demand": forecast_quantity,
                    "is_forecast": True,
                }
            )
            week = _next_week(week)

        product_series.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "trend": forecast["trend"],
                "confidence_level": forecast["confidence_level"],
                "series": points,
            }
        )

    return {"products": product_series}
```

- [ ] **Step 4: Run the full forecasting test module and confirm the known-broken set**

Run: `cd backend && python -m pytest tests/test_forecast_weekly.py -q`
Expected: the `quantity_produced`-asserting tests listed in Task 3 Step 1 FAIL (they assert a field this function no longer returns from `get_weekly_historical_demand`) — every other test in this file passes unchanged. This confirms the blast radius is exactly what Task 3 accounts for, nothing more.

- [ ] **Step 5: Commit together with Task 1's schema change**

```bash
git add backend/app/schemas/forecast.py backend/app/services/forecasting.py
git commit -m "feat: merge weekly forecast buckets with ledger-sourced production series"
```

---

### Task 3: Backend tests — migrate the `quantity_produced` assertions off `get_weekly_historical_demand`

**Files:**
- Modify: `backend/tests/test_forecast_weekly.py` (strip `quantity_produced` from existing `get_weekly_historical_demand` assertions; the dedicated `test_quantity_produced_is_summed_independently_of_quantity_sold` test moves to target `get_weekly_produced_demand` instead)
- Modify/retire: `backend/tests/test_forecast_production_series.py` (every test calling `get_transaction_historical_demand` or asserting monthly-period production events needs rewriting against the new weekly functions - see Step 3)
- Modify/retire: `backend/tests/test_forecast_timeseries_production.py` (asserts the monthly/single-forecast-point `get_forecast_timeseries` shape directly - needs rewriting against the weekly/3-point shape)
- Test: this task's own deliverable IS the test suite

**Interfaces:**
- Consumes: `get_weekly_historical_demand`, `get_weekly_produced_demand` (Task 2).

- [ ] **Step 1: In `test_forecast_weekly.py`, remove `quantity_produced` from every `get_weekly_historical_demand` result assertion**

Every dict literal under a `get_weekly_historical_demand(db)[product.id]` assertion (lines 73, 99, 104, 130, 135, 140, 172, 219, 274, 282, 287 per the pre-integration file) drops its `"quantity_produced": Decimal("...")` key - the function no longer returns it, so the expected-dict literals must match the trimmed shape (`{"period": ..., "quantity": ...}` only).

- [ ] **Step 2: Move `test_quantity_produced_is_summed_independently_of_quantity_sold` to target `get_weekly_produced_demand`**

The existing test (line 148) built two same-week transactions with different `quantity`/`quantity_produced` and asserted the latter summed independently. Rewrite it as a pre-rollout-only scenario (no ledger application exists in this test, so both transactions must have `production_cycle_id=None` for their `quantity_produced` to count at all under the new sourcing rule):

```python
def test_weekly_produced_sums_legacy_pre_rollout_rows_independently_of_sold(
    db, test_products,
):
    product = test_products[0]

    _make_transaction(
        product.id, datetime(2026, 1, 5), quantity=3,
        quantity_produced=10,
    )
    _make_transaction(
        product.id, datetime(2026, 1, 6), quantity=2,
        quantity_produced=7,
    )

    produced = get_weekly_produced_demand(db)[product.id]

    assert produced == [
        {"period": "2026-01-05", "quantity_produced": Decimal("17")},
    ]
```

(`_make_transaction` is this file's existing fixture helper at line 12 - confirm it leaves `production_cycle_id` at its model default of `None`, which it does; the helper never sets that column.)

- [ ] **Step 3: Add a dedicated `get_weekly_produced_demand` ledger-sourcing test**

```python
def test_weekly_produced_sums_ledger_applications_by_applied_week(
    db, test_products, two_cycles,
):
    from conftest import apply_production_to_cycle

    first, _second = two_cycles
    product = test_products[0]

    apply_production_to_cycle(db, first.id, product.id, 6)
    apply_production_to_cycle(db, first.id, product.id, 4)

    produced = get_weekly_produced_demand(db)[product.id]

    week_of_first_cycle = _week_start(first.start_date).strftime(
        "%Y-%m-%d"
    )

    assert produced == [
        {
            "period": week_of_first_cycle,
            "quantity_produced": Decimal("10"),
        },
    ]
```

(Requires importing `_week_start` and `get_weekly_produced_demand` from `app.services.forecasting`, and the `two_cycles` fixture from `conftest.py` - already used by `test_transaction_cycle_resolution.py`/`test_transaction_stock.py`.)

- [ ] **Step 4: Retire the monthly-period production tests in `test_forecast_production_series.py`**

Every test there calling `get_production_event_series` (a function this plan removes - its responsibility is absorbed into `get_weekly_produced_demand`) or `get_transaction_historical_demand` (also removed - absorbed into the trimmed `get_weekly_historical_demand` plus the legacy half of `get_weekly_produced_demand`) needs its *intent* preserved against the new function names, not deleted outright. Walk each test: if it asserts "a ledger application appears as a production event dated by applied_at" → re-target `get_weekly_produced_demand` and assert the week bucket instead of the exact day. If it asserts "a pre-rollout row's quantity_produced still shows, a post-rollout row's doesn't" → re-target `get_weekly_produced_demand` (pre-rollout row contributes) and `get_weekly_historical_demand` (post-rollout row's `quantity_produced` is simply absent from the return shape now, not nulled - assert the key is gone, not that it's `None`).

- [ ] **Step 5: Retire `test_forecast_timeseries_production.py`'s monthly/single-point assertions**

This file asserts the OLD `get_forecast_timeseries` response shape (monthly periods, one trailing forecast point, `transaction_id`/`application_id` present on points). Re-run each test's scenario against the new weekly/3-point/no-identity-fields shape: period strings become week-Mondays, `assert len(points) == history + 1` becomes `assert len(points) == history + WEEKLY_FORECAST_WEEKS`, and any assertion reading `point["application_id"]`/`point["transaction_id"]` is dropped (those fields no longer exist on the combined schema - Task 1).

- [ ] **Step 6: Run the full suite**

Run: `cd backend && python -m pytest tests/test_forecast.py tests/test_forecast_weekly.py tests/test_forecast_production_series.py tests/test_forecast_timeseries_production.py tests/test_forecast_chat.py tests/test_forecast_history.py tests/test_forecast_aggregation.py -q`
Expected: PASS, 0 failures.

- [ ] **Step 7: Commit**

```bash
git add backend/tests/test_forecast_weekly.py backend/tests/test_forecast_production_series.py backend/tests/test_forecast_timeseries_production.py
git commit -m "test: migrate forecasting tests to the weekly sold/produced split"
```

---

### Task 4: Frontend types — combined `ForecastTimeSeriesPoint`

**Files:**
- Modify: `frontend/src/pages/demand-forecasting/api/forecastTypes.ts`

**Interfaces:**
- Produces: `ForecastPointType = 'SALE' | 'PRODUCTION' | 'FORECAST'`, `ForecastTimeSeriesPoint { period, point_type, historical_sales, quantity_produced, predicted_demand, is_forecast }`, `ProductTimeSeriesResponse { product_id, product_name, trend, confidence_level, series }` - consumed by Task 5.

- [ ] **Step 1: Replace the point and series interfaces**

```typescript
// point_type is the authoritative kind discriminator (see
// backend/app/schemas/forecast.py):
//   SALE       - one calendar week's sold total (zero-filled).
//                historical_sales is the quantity SOLD.
//                quantity_produced is always null here.
//   PRODUCTION - one calendar week's produced total (ledger-sourced,
//                plus the pre-rollout legacy fallback). Never
//                zero-filled - a week with no production has no
//                PRODUCTION point. quantity_produced is the quantity
//                PRODUCED.
//   FORECAST   - one of the three trailing weekly projections.
// is_forecast stays available and is true exactly when point_type is
// 'FORECAST'. Per-event identity (transaction/application ids) does
// not survive weekly aggregation and is not part of this shape.
export type ForecastPointType = 'SALE' | 'PRODUCTION' | 'FORECAST'

export interface ForecastTimeSeriesPoint {
  period: string
  point_type: ForecastPointType
  historical_sales: string | null
  quantity_produced: string | null
  predicted_demand: string | null
  is_forecast: boolean
}

export interface ProductTimeSeriesResponse {
  product_id: number
  product_name: string
  // Computed once from the product's weekly sold series and shared
  // by every forecast point in `series` - never per-point.
  trend: string
  confidence_level: string
  series: ForecastTimeSeriesPoint[]
}
```

- [ ] **Step 2: Run the TypeScript build to confirm the expected downstream breakage**

Run: `cd frontend && npx tsc -b`
Expected: errors in `forecastAdapter.ts` (Task 5) and any file reading the removed `transaction_id`/`transaction_number`/`application_id`/`application_number`/`production_cycle_id` fields - this confirms the type change's blast radius matches Task 5/6/7's scope and nothing wider.

- [ ] **Step 3: Commit together with Task 5 - do not commit yet, continue directly**

---

### Task 5: Frontend adapter — merged chart data + the `toUiForecastTableItems` fix

**Files:**
- Modify: `frontend/src/pages/demand-forecasting/api/forecastAdapter.ts`
- Test: `frontend/src/pages/demand-forecasting/api/forecastAdapter.test.ts` (Task 7)

**Interfaces:**
- Consumes: `ForecastTimeSeriesPoint`, `ProductTimeSeriesResponse` (Task 4).
- Produces: `toUiForecastChartData(series) -> ForecastChartData[]`, `toUiForecastTableItems(timeseries) -> ForecastTableItem[]` - consumed by `ForecastChart.tsx`/the forecast table component (Task 6, unchanged caller signatures).

- [ ] **Step 1: Update `toUiForecastChartData`**

```typescript
export function toUiForecastChartData(
  series: ForecastTimeSeriesPoint[],
): ForecastChartData[] {
  return series.map((point) => ({
    date: formatAxisLabel(point.period),
    fullDate: formatFullDate(point.period),
    pointType: point.point_type,
    isForecast: point.is_forecast,
    historicalDemand: point.point_type === 'SALE'
      ? parseNullableDecimal(point.historical_sales)
      : undefined,
    producedQuantity: point.point_type === 'PRODUCTION'
      ? parseNullableDecimal(point.quantity_produced)
      : undefined,
    forecastedDemand: point.is_forecast
      ? parseNullableDecimal(point.predicted_demand)
      : undefined,
  }))
}
```

(`transactionNumber`/`applicationNumber` are dropped from `ForecastChartData` in `types.ts` alongside this - no per-event identity survives weekly aggregation, per the architecture section above.)

- [ ] **Step 2: Fix `toUiForecastTableItems` to filter on `point_type`, not `is_forecast` alone**

```typescript
export function toUiForecastTableItems(
  timeseries: ForecastTimeSeriesResponse | undefined,
): ForecastTableItem[] {
  if (!timeseries) {
    return []
  }

  return timeseries.products.map((product) => {
    // Filtered to SALE specifically, not merely "not a forecast
    // point" - a PRODUCTION point is also non-forecast, and picking
    // it here would read historical_sales as null and silently
    // report 0 sold for a product that was recently produced but
    // hasn't sold yet this week.
    const salePoints = product.series.filter(
      (point) => point.point_type === 'SALE',
    )
    const forecastPoints = product.series.filter(
      (point) => point.is_forecast,
    )

    const latestSale = salePoints.at(-1)
    const firstForecast = forecastPoints[0]

    return {
      id: product.product_id,
      furnitureProduct: product.product_name,
      historicalSales: latestSale
        ? parseDecimal(latestSale.historical_sales ?? '0')
        : 0,
      predictedDemand: firstForecast
        ? Math.ceil(
            parseDecimal(firstForecast.predicted_demand ?? '0'),
          )
        : 0,
      forecastPeriod: firstForecast
        ? formatWeekRangeLabel(firstForecast.period)
        : '—',
      confidenceLevel: parseDecimal(product.confidence_level),
    }
  })
}
```

(`weekEndIso`/`formatWeekRangeLabel` are `main`'s existing helpers in this file - unchanged, reused as-is.)

- [ ] **Step 3: Run the TypeScript build**

Run: `cd frontend && npx tsc -b`
Expected: PASS (0 errors) once Task 6 also lands - commit Tasks 4/5/6 together since the type/adapter/component chain can't type-check independently.

---

### Task 6: Frontend chart component — three series + production-aware empty state

**Files:**
- Modify: `frontend/src/pages/demand-forecasting/components/ForecastChart.tsx`
- Modify: `frontend/src/pages/demand-forecasting/types.ts` (`ForecastChartData` shape)
- Test: `frontend/src/pages/demand-forecasting/components/ForecastChart.test.tsx` (Task 7)

**Interfaces:**
- Consumes: `ForecastChartData` (this task redefines it), `toUiForecastChartData` (Task 5).

- [ ] **Step 1: Redefine `ForecastChartData` in `types.ts`**

```typescript
export interface ForecastChartData {
  date: string
  fullDate: string
  pointType: 'SALE' | 'PRODUCTION' | 'FORECAST'
  isForecast: boolean
  historicalDemand?: number
  producedQuantity?: number
  forecastedDemand?: number
}
```

(Drops `transactionNumber`/`applicationNumber`/`quantityProduced` from both branches' versions - no per-event identity survives weekly aggregation, and `quantityProduced`'s old "sold-point tooltip extra" role is now fully covered by the separate `producedQuantity` series on its own `PRODUCTION` points.)

- [ ] **Step 2: Add the third series and update the tooltip/empty-state**

In the series list (wherever `main`'s two-entry array currently sits), insert the production series between historical and forecast:

```typescript
const series = [
  { name: 'historicalDemand', label: 'Historical Demand (Weekly)' },
  { name: 'producedQuantity', label: 'Applied Production', color: 'teal.6' },
  { name: 'forecastedDemand', label: 'Forecasted Demand', strokeDasharray: '5 5' },
]
```

Tooltip branch per `pointType` (replacing whatever `isForecast`-only branching exists today):

```typescript
{row.pointType === 'SALE' && (
  <Text size="sm">Quantity sold: {row.historicalDemand} units</Text>
)}
{row.pointType === 'PRODUCTION' && (
  <Text size="sm">Quantity produced: {row.producedQuantity} units</Text>
)}
{row.pointType === 'FORECAST' && (
  <Text size="sm">Forecasted demand: {row.forecastedDemand} units</Text>
)}
```

Empty-state message (wherever the component currently renders "no data" for a product with zero plottable points): change the condition from "no historical points" to "no SALE and no PRODUCTION points", and the copy to `"No sales or production recorded"` (the ledger branch's wording) - a product produced but never sold must not hit the empty state.

- [ ] **Step 3: Run the TypeScript build and the chart test file**

Run: `cd frontend && npx tsc -b && npx vitest run src/pages/demand-forecasting/components/ForecastChart.test.tsx`
Expected: `tsc` passes; the test file fails until Task 7 updates its fixtures to the new shape - expected at this point.

---

### Task 7: Frontend tests — combined fixtures for the chart and adapter

**Files:**
- Modify: `frontend/src/pages/demand-forecasting/components/ForecastChart.test.tsx`
- Modify: `frontend/src/pages/demand-forecasting/api/forecastAdapter.test.ts`
- Modify: `frontend/src/pages/demand-forecasting/hooks/useForecast.test.tsx` (uses chart/adapter fixtures indirectly - verify after the other two)
- Modify: `frontend/src/pages/demand-forecasting/DemandForecastingPage.test.tsx` (same)

**Interfaces:**
- Consumes: everything from Tasks 4-6.

- [ ] **Step 1: Rewrite `ForecastChart.test.tsx` fixtures around weekly + three-series data**

Combine `main`'s weekly fixture shape with the ledger's production-row addition:

```typescript
const sale = (
  date: string,
  fullDate: string,
  sold: number,
): ForecastChartData => ({
  date,
  fullDate,
  pointType: 'SALE',
  isForecast: false,
  historicalDemand: sold,
})

const produced = (
  date: string,
  fullDate: string,
  quantity: number,
): ForecastChartData => ({
  date,
  fullDate,
  pointType: 'PRODUCTION',
  isForecast: false,
  producedQuantity: quantity,
})

const forecastWeek = (
  date: string,
  fullDate: string,
  predicted: number,
): ForecastChartData => ({
  date,
  fullDate,
  pointType: 'FORECAST',
  isForecast: true,
  forecastedDemand: predicted,
})

const WEEKLY_ROWS: ForecastChartData[] = [
  produced('Jan 05', 'Jan 05, 2026', 12),
  sale('Jan 05', 'Jan 05, 2026', 10),
  sale('Jan 12', 'Jan 12, 2026', 0),
  sale('Jan 19', 'Jan 19, 2026', 20),
  forecastWeek('Jan 26', 'Jan 26, 2026', 25),
  forecastWeek('Feb 02', 'Feb 02, 2026', 30),
  forecastWeek('Feb 09', 'Feb 09, 2026', 35),
]
```

Carry `main`'s existing x-axis/tick/thinning assertions forward unchanged (they key off array length and `tickFormatter`, which still work with 7 rows instead of 6 - update the expected length/label lists to match). Carry the ledger's three dedicated production tests (`renders the chart when a product has production but no sales`, `still explains an entirely empty product`, `shows the applied production figure...`) forward, dropping the `applicationNumber`/`PA-0007` assertion specifically (no longer part of the shape - assert only the `"Quantity produced: 6 units"` tooltip line).

- [ ] **Step 2: Rewrite `forecastAdapter.test.ts` fixtures to cover the `toUiForecastTableItems` SALE-vs-PRODUCTION fix**

Add a regression test proving the bug this integration fixes:

```typescript
it('uses the latest SALE point for historicalSales even when a later PRODUCTION point exists', () => {
  const timeseries: ForecastTimeSeriesResponse = {
    products: [
      {
        product_id: 1,
        product_name: 'Ordinary Chair',
        trend: 'STABLE',
        confidence_level: '80.00',
        series: [
          {
            period: '2026-01-05',
            point_type: 'SALE',
            historical_sales: '10',
            quantity_produced: null,
            predicted_demand: null,
            is_forecast: false,
          },
          {
            period: '2026-01-12',
            point_type: 'PRODUCTION',
            historical_sales: null,
            quantity_produced: '5',
            predicted_demand: null,
            is_forecast: false,
          },
          {
            period: '2026-01-19',
            point_type: 'FORECAST',
            historical_sales: null,
            quantity_produced: null,
            predicted_demand: '12',
            is_forecast: true,
          },
        ],
      },
    ],
  }

  const items = toUiForecastTableItems(timeseries)

  expect(items[0].historicalSales).toBe(10)
})
```

Update every existing fixture in this file to the combined point shape (`point_type` instead of `transaction_number`/`application_number`-bearing rows), per Task 4's interface.

- [ ] **Step 3: Run the full frontend demand-forecasting suite**

Run: `cd frontend && npx tsc -b && npx vitest run src/pages/demand-forecasting`
Expected: PASS, 0 failures.

- [ ] **Step 4: Commit Tasks 4-7 together**

```bash
git add frontend/src/pages/demand-forecasting
git commit -m "feat: render ledger-sourced production as its own weekly forecast series"
```

---

## Conflict resolution strategy

The 5 previously-conflicting files resolve as follows once Tasks 1-7 land on a branch built from `feat/production-inventory-ledger`'s tip merged with `main`:

| File | Resolution |
|---|---|
| `backend/app/schemas/forecast.py` | Task 1's combined classes - supersede both sides' versions entirely. |
| `backend/app/services/forecasting.py` | Task 2's three functions - supersede both sides' `get_weekly_historical_demand`/`get_transaction_historical_demand`/`get_production_event_series`/`get_forecast_timeseries`. |
| `frontend/.../api/forecastTypes.ts` | Task 4's combined interfaces. |
| `frontend/.../api/forecastAdapter.test.ts` | Task 7 Step 2's rewritten fixtures. |
| `frontend/.../components/ForecastChart.test.tsx` | Task 7 Step 1's rewritten fixtures. |

Mechanically, during the actual `git merge`: for each of these 5 files, discard both `<<<<<<< HEAD`/`>>>>>>> origin/feat/production-inventory-ledger` sides entirely and replace the file's conflicting region with the Task 1/2/4/7 content above (the non-conflicting surrounding code in each file - imports, unrelated functions - is kept as whichever side introduced it, same as the merge already does automatically outside the marked regions).

---

## Test plan

**Backend (run from `backend/`, against `armando_furniture_test` - `conftest.py` enforces this automatically):**
- `pytest tests/test_forecast_weekly.py` - Task 3
- `pytest tests/test_forecast_production_series.py` - Task 3
- `pytest tests/test_forecast_timeseries_production.py` - Task 3
- `pytest tests/test_forecast.py tests/test_forecast_chat.py tests/test_forecast_history.py tests/test_forecast_aggregation.py` - regression guard, untouched by this plan but downstream of the same module
- Full suite: `pytest -q` - must stay at the pre-integration pass count (537 on the ledger branch alone; `main`'s own suite count needs a baseline run before merging, since this plan hasn't measured it)

**Frontend (run from `frontend/`):**
- `npx tsc -b` - must be clean
- `npx vitest run src/pages/demand-forecasting` - Task 7
- `npx vitest run` (full suite) - regression guard for everything else untouched by this plan (production-allocation, transaction-history, inventory, opening-inventory pages)

**New integration-specific test added by this plan:** Task 7 Step 2's `toUiForecastTableItems` regression test is the one case neither branch's own test suite would have caught on its own - it only exists because combining both branches' designs creates a new failure mode (a PRODUCTION point masquerading as the "latest historical" point). This is the single most important test in the whole plan.

---

## Risks and dependencies

- **`backend/docs/demand-forecasting-api-contract.md` diverges on both branches** (confirmed via `git grep` - both sides have their own version documenting the old contract). Not code, not blocking, but should be rewritten to document the combined weekly+ledger contract once this plan lands - flagged here, not scheduled as a task, since the user's restrictions for this round are plan-only.
- **`get_transaction_historical_demand` and `get_production_event_series` are removed function names.** Any caller outside the files already identified (checked via `git grep` on both branches - routers/forecast.py calls only `get_forecast_timeseries`, never the two removed functions directly) would break silently if one exists elsewhere and was missed. Re-run the same `git grep` after the actual merge's auto-merged ~90 files land, before finalizing Task 2, to catch anything introduced by a file this plan didn't review in detail.
- **Weekly bucketing discards per-application identity for production**, same as it already discards per-transaction identity for sales. If a future requirement needs "which exact application produced these units this week," that information still exists in `production_application_items`/`production_applications` directly - it's just no longer surfaced through the forecast timeseries endpoint. Worth flagging to the user as a product decision already implicitly made by `main`'s original weekly design, now extended to production.
- **No migration risk.** Confirmed via `git diff --name-status` against the merge base that `main` added zero Alembic revisions since the fork - only the ledger branch's existing 3 migrations apply, and both `armando_furniture` and `armando_furniture_test` are already stamped at the ledger branch's tip (`9733160b3d9a`), verified in an earlier investigation this session. Merging requires no `alembic upgrade` against any database.
- **The other ~90 auto-merging files are not re-verified by this plan.** They merged with zero conflicts in the earlier aborted attempt, which is strong evidence they're independent, but this plan's test commands (Task 2 Step 4, Task 3 Step 6, full-suite runs) are what actually proves it - don't skip the full-suite runs on the assumption that a clean auto-merge implies correctness.

---

## Recommended implementation sequence

1. Tasks 1 → 2 → 3 (backend: schema, service, tests) - land and verify fully in isolation first, since the frontend tasks depend on the backend's final field names (`point_type`, the dropped identity fields) being settled.
2. Tasks 4 → 5 → 6 → 7 (frontend: types, adapter, component, tests) - in that order, since each depends on the previous task's interface.
3. Perform the actual `git merge origin/feat/production-inventory-ledger` into `main` (or a working branch cut from it), then replace each of the 5 conflicted files' conflicting regions with this plan's Task 1/2/4/7 output exactly as written in "Conflict resolution strategy" above.
4. Run the full backend suite (`pytest -q`) and full frontend suite (`tsc -b && vitest run`) against the merged tree.
5. Re-run the `git grep` from "Risks and dependencies" against the merged tree specifically (not just the two source branches) to catch any caller introduced by one of the ~90 auto-merged files that this plan didn't review line-by-line.
6. Only after all of the above pass: commit the merge, with the user's explicit approval, exactly as this session has done for every commit/push so far.

# Armando Furniture Business Backend — Final Implementation Plan

## Purpose

This is the final backend implementation plan based on the approved UI screenshots for:

- Dashboard
- Resources
- Products
- Production Allocation
- Resource Utilization
- Transaction History
- Optimization History
- Demand Forecasting

The goal is to freeze the backend architecture and API contract before frontend integration and avoid repeated revisions.

---

# 1. Final System Structure

```text
                    PRODUCTS
                       |
                       +------------------+
                       |                  |
                       v                  v
                 RESOURCES        SALES TRANSACTIONS
                       |                  |
                       v                  v
              PRODUCT RESOURCE      DEMAND FORECAST
                REQUIREMENTS              |
                       |                  v
                       |           FORECAST HISTORY
                       |
                       v
                PRODUCTION CYCLE
                       |
                       +------------------+
                       |                  |
                       v                  v
             PRODUCTION ALLOCATION    RESOURCE
                       |              UTILIZATION
                       v
                  OPTIMIZATION
                       |
                 +-----+-----+
                 |           |
                 v           v
          OPTIMIZATION    PRODUCTION
             HISTORY       RESULTS
                 |           |
                 +-----+-----+
                       |
                       v
                   DASHBOARD
```

---

# 2. Existing Database Tables — KEEP

Do not redesign these core tables:

```text
products
resources
product_resource_requirements
production_cycles
cycle_resources
production_allocations
optimization_runs
optimization_results
sales_transactions
forecast_runs
forecast_results
```

---

# 3. API Status — Current vs Final

## 3.1 Products — DONE

```http
GET    /api/products
GET    /api/products/{product_id}
POST   /api/products
PUT    /api/products/{product_id}
DELETE /api/products/{product_id}
```

Supports the Products screen.

---

## 3.2 Resources — DONE

```http
GET    /api/resources
GET    /api/resources/{resource_id}
POST   /api/resources
PUT    /api/resources/{resource_id}
DELETE /api/resources/{resource_id}
```

Supports Resource Type, Available Quantity, Unit Price, and Actions.

---

## 3.3 Product Resource Requirements — DONE

```http
GET    /api/product-resources
GET    /api/product-resources/{id}
POST   /api/product-resources
PUT    /api/product-resources/{id}
DELETE /api/product-resources/{id}
```

Provides material, labor, and machine requirements used by Products and Optimization.

---

## 3.4 Production Cycles — DONE

```http
GET    /api/production-cycles
GET    /api/production-cycles/{cycle_id}
POST   /api/production-cycles
PUT    /api/production-cycles/{cycle_id}
DELETE /api/production-cycles/{cycle_id}
```

Represents a production planning cycle.

---

## 3.5 Cycle Resources — DONE

```http
GET    /api/cycle-resources
POST   /api/cycle-resources
PUT    /api/cycle-resources/{id}
DELETE /api/cycle-resources/{id}
```

Provides resource availability and capacity for a production cycle.

---

## 3.6 Production Allocation — DONE

```http
GET    /api/allocations/{cycle_id}
GET    /api/allocations/{cycle_id}/{product_id}
POST   /api/allocations/{cycle_id}
PUT    /api/allocations/{cycle_id}/{product_id}
DELETE /api/allocations/{cycle_id}/{product_id}
```

Supports:

```text
Furniture Type
Quantity to Produce
```

and feeds Optimization.

---

# 4. Optimization — CORE DONE

The optimization execution and result functionality is implemented and tested.

Database:

```text
optimization_runs
optimization_results
```

Existing optimization execution endpoints remain unchanged.

---

# 5. Optimization History — REPORTING REMAINING

## Existing database

### optimization_runs

```text
id
production_cycle_id
started_at
completed_at
duration_ms
status
objective_value
total_profit
```

### optimization_results

```text
optimization_run_id
product_id
recommended_quantity
unit_profit
total_profit
```

## Final API

Implement:

```http
GET /api/optimization/history
GET /api/optimization/history/{run_id}
GET /api/optimization/history/latest
```

## Final response

Approximately:

```json
{
  "optimization_id": "OP-220",
  "date_generated": "2026-06-06T08:16:02",
  "duration_ms": 812,
  "total_profit": 96720,
  "total_production_cost": 188680,
  "products_produced": 57
}
```

## Calculated fields

Optimization ID:

```python
optimization_id = f"OP-{run.id}"
```

Products Produced:

```python
products_produced = sum(
    result.recommended_quantity
    for result in run.results
)
```

Do not immediately add `total_production_cost` to the database. First calculate it from optimization result/product/resource data. Persist it only if historical results cannot be reconstructed reliably.

The same history response should provide enough data for the projected profit trend chart.

### Status

**REPORTING API REMAINING**

---

# 6. Sales / Transaction History — MODEL + API REMAINING

The UI requires:

```text
Transaction #
Date
Furniture Product
Quantity Produced
Sold
Sales
Production Cost
Profit Earned
```

## Recommended final structure

```text
sales_transactions
├── id
├── transaction_number
├── transaction_date
├── product_id
├── quantity_produced
├── quantity_sold
├── unit_price
├── total_sales
├── production_cost
└── total_profit
```

`unit_profit` can be retained if useful.

## API

```http
GET    /api/transactions
GET    /api/transactions/{transaction_id}
POST   /api/transactions
PUT    /api/transactions/{transaction_id}
DELETE /api/transactions/{transaction_id}
```

Optional query parameters:

```http
GET /api/transactions?search=Dining
GET /api/transactions?start_date=...
GET /api/transactions?end_date=...
```

Do not create separate search endpoints.

## Important business distinction

The system must distinguish:

```text
Quantity Produced
```

from:

```text
Quantity Sold
```

because production and sales are separate business events.

### Status

**DATABASE + SCHEMA + SERVICE + TESTS REMAINING**

---

# 7. Resource Utilization — REPORTING REMAINING

The UI requires:

```text
Overall Utilization Rate
Total Raw Materials Consumed
Total Labor Hours Used
Total Machine Hours Used
```

and:

```text
Resource
Total Consumedcd
Total Remaining
Overall Utilization %
```

plus:

```text
Bottleneck Analysis
```

## Existing tables are sufficient

Use:

```text
resources
cycle_resources
product_resource_requirements
production_allocations
optimization_results
```

## New reporting endpoint

Recommended:

```http
GET /api/resource-utilization
```

Potentially, if tied to a specific production cycle:

```http
GET /api/resource-utilization/{cycle_id}
```

## Example response

```json
{
  "overall_utilization_rate": 81.4,
  "total_raw_materials_consumed": 2150,
  "total_labor_hours_used": 480,
  "total_labor_hours_capacity": 576,
  "total_machine_hours_used": 310,
  "total_machine_hours_capacity": 672,
  "resources": [],
  "bottlenecks": []
}
```

No new database table is required initially.

### Status

**REPORTING SERVICE + API + TESTS REMAINING**

---

# 8. Demand Forecasting — MAJOR UPGRADE REMAINING

## Existing APIs — KEEP

```http
GET  /api/forecast
POST /api/forecast/generate
GET  /api/forecast/history
GET  /api/forecast/history/latest
GET  /api/forecast/history/{run_id}
```

Forecast History has already been implemented.

## Current limitation

The current algorithm essentially uses:

```text
historical quantities
        |
        v
latest quantity
        |
        v
trend
        |
        v
forecast
```

This is insufficient for the final UI.

The UI requires monthly historical data and future forecast data.

---

# 9. Final Forecast Response

The Forecast Table needs:

```text
Furniture Product
Historical Sales
Predicted Demand
Forecast Period
Confidence Level
Forecast Status
```

Recommended model:

```python
ProductForecast:
    product_id
    product_name
    historical_sales
    predicted_demand
    forecast_period
    confidence_level
    forecast_status
    trend
```

---

# 10. Forecast Time Series

The graph requires historical and forecasted monthly data:

```text
Jan 2026
Feb 2026
Mar 2026
Apr 2026
May 2026
Jun 2026
Jul 2026
Aug 2026
```

Flow:

```text
SalesTransaction
        |
        v
Monthly aggregation
        |
        v
Historical monthly demand
        |
        v
Forecast calculation
        |
        v
Future monthly demand
```

Do not build the frontend graph until this backend structure is finalized.

---

# 11. Forecast Confidence

Add:

```text
confidence_level
```

to forecast results.

The value should be calculated deterministically based on historical data quality and consistency.

Do not represent it as an AI probability unless the actual forecasting model produces a statistically valid confidence measure.

---

# 12. Forecast Status

Add:

```text
forecast_status
```

Possible values:

```text
READY
LOW_CONFIDENCE
NO_DATA
```

---

# 13. Forecast Database

Keep:

```text
forecast_runs
forecast_results
```

Adjust `forecast_results` to include:

```text
confidence_level
forecast_status
```

Potentially include forecast period at the result level if individual product forecasts can have different periods.

### Status

**FORECAST ENGINE + SCHEMA + TESTS REMAINING**

Forecast History itself is already implemented.

---

# 14. Dashboard — FINAL AGGREGATION REMAINING

Keep:

```http
GET /api/dashboard/summary
```

## Final Dashboard data

### KPI cards

```text
total_available_resources
expected_revenue
expected_profit
waste_percentage
```

### Production recommendations

```text
production_recommendations
```

Each recommendation:

```text
product_name
recommended_quantity
expected_profit
```

### Resource utilization

```text
resource_utilization
```

Existing metrics can remain if useful:

```text
total_products
total_resources
total_production_cycles
total_allocations
total_optimization_runs
total_sales
total_sales_profit
```

## Dashboard calculations

Dashboard should aggregate/report data from existing services instead of containing complex business logic.

Conceptually:

```text
Dashboard Service
       |
       +-- Optimization results
       +-- Resource utilization
       +-- Sales totals
       +-- Production recommendations
       +-- Forecast information if required
```

Values must come from real database/optimization data, not hardcoded values.

Example UI values:

```text
Total Available Resources
1,248 units

Expected Revenue
₱285,400

Expected Profit
₱96,720

Waste Percentage
4.8%
```

and:

```text
Dining Table       12 units    ₱36,000
Wardrobe            6 units    ₱24,000
Bookshelf          15 units    ₱18,000
Carved Chair       24 units    ₱18,720
```

### Status

**DASHBOARD FINAL AGGREGATION REMAINING**

---

# 15. Final API Map

## CRUD APIs — DONE / EXISTING

```text
/api/products
/api/resources
/api/product-resources
/api/production-cycles
/api/cycle-resources
/api/allocations
/api/transactions
```

`/api/transactions` still requires the final transaction model adjustment.

## Optimization — CORE DONE

```text
/api/optimization/...
```

### Reporting to add

```text
GET /api/optimization/history
GET /api/optimization/history/{run_id}
GET /api/optimization/history/latest
```

## Forecast — EXISTING, NEEDS UPGRADE

```text
GET  /api/forecast
POST /api/forecast/generate
GET  /api/forecast/history
GET  /api/forecast/history/latest
GET  /api/forecast/history/{run_id}
```

Do not create duplicate forecast endpoints.

## Reporting — REMAINING

```text
GET /api/resource-utilization
GET /api/optimization/history
```

## Dashboard — EXISTING, NEEDS EXPANSION

```text
GET /api/dashboard/summary
```

Keep one main dashboard endpoint rather than creating many dashboard-specific endpoints unless performance later requires it.

---

# 16. Final Database Changes

## sales_transactions

Add/adjust:

```text
transaction_number
quantity_produced
quantity_sold
production_cost
```

while retaining useful existing financial fields.

## forecast_results

Add:

```text
confidence_level
forecast_status
```

Potentially add forecast-period/time-series structure depending on the final forecasting implementation.

## optimization_runs

**No change initially.**

Calculate production cost from existing data first.

---

# 17. Final Implementation Order

## Phase 1 — Transaction History

1. Adjust SalesTransaction model
2. Create Alembic migration
3. Update transaction schemas
4. Update transaction service
5. Update transaction endpoints
6. Add transaction tests
7. Run full pytest
8. Commit

Do not move on until stable.

---

## Phase 2 — Resource Utilization

1. Define response schema
2. Implement utilization calculation
3. Implement bottleneck calculation
4. Implement endpoint
5. Add tests
6. Run full pytest
7. Commit

---

## Phase 3 — Optimization History

1. Define history response schema
2. Calculate `OP-xxx` ID
3. Calculate products produced
4. Calculate production cost
5. Create history endpoint
6. Create single-run endpoint
7. Create latest endpoint
8. Add profit trend data
9. Add tests
10. Run full pytest
11. Commit

---

## Phase 4 — Demand Forecasting

1. Aggregate monthly historical sales
2. Define forecast algorithm
3. Generate future demand
4. Calculate trend
5. Calculate confidence
6. Determine forecast status
7. Update ForecastResult schema
8. Update forecast database if required
9. Update `/api/forecast`
10. Update `/api/forecast/generate`
11. Preserve forecast history endpoints
12. Add time-series response
13. Add tests
14. Run full pytest
15. Commit

---

## Phase 5 — Dashboard

Only after Phases 1–4 are complete:

1. Define final Dashboard schema
2. Connect optimization recommendations
3. Connect expected revenue
4. Connect expected profit
5. Connect resource availability
6. Connect resource utilization
7. Calculate waste percentage
8. Add resource utilization data
9. Add production recommendations
10. Update `/api/dashboard/summary`
11. Add tests
12. Run full pytest
13. Commit

---

# 18. Final Backend Validation

After all phases:

```powershell
python -m pytest -v
```

Target:

```text
ALL TESTS PASSED
```

Verify the main endpoints:

```text
GET /api/products
GET /api/resources
GET /api/product-resources
GET /api/production-cycles
GET /api/cycle-resources
GET /api/allocations
GET /api/transactions
GET /api/optimization/history
GET /api/resource-utilization
GET /api/forecast
GET /api/forecast/history
GET /api/forecast/history/latest
GET /api/dashboard/summary
```

Then verify Alembic:

```powershell
python -m alembic current
```

The database should be at the expected `HEAD`.

---

# 19. Final Status

## DONE

```text
Products
Resources
Product Resource Requirements
Production Cycles
Cycle Resources
Production Allocations
Optimization Engine
Optimization History database
Forecast Engine - basic version
Forecast History
Dashboard basic summary
Sales Transactions - basic version
Alembic setup
Tests
```

## NEEDS COMPLETION

```text
Transaction History final data model/API
Resource Utilization reporting
Optimization History reporting API
```

## NEEDS SUBSTANTIAL IMPLEMENTATION

```text
Demand Forecasting final algorithm/time series
Forecast confidence/status
Dashboard final aggregation
```

---

# 20. Development Rule Going Forward

Treat the screenshots as the **final UI contract**.

For every backend field, define the complete chain:

```text
UI field
    |
    v
API response field
    |
    v
Service calculation
    |
    v
Database source
```

Example:

```text
Dashboard:
Expected Profit
    |
    v
expected_profit
    |
    v
latest optimization
    |
    v
optimization_runs.total_profit
```

Transaction:

```text
Production Cost
    |
    v
production_cost
    |
    v
SalesTransaction.production_cost
```

Forecast:

```text
Predicted Demand
    |
    v
predicted_demand
    |
    v
forecast calculation
    |
    v
monthly sales history
```

This prevents implementing an endpoint and later discovering that the frontend needs a completely different data structure.

---

# 21. Final Sequence

```text
                    CURRENT
                       |
                       v
             +-------------------+
             | Transaction       |
             | History           |
             +---------+---------+
                       |
                       v
             +-------------------+
             | Resource          |
             | Utilization       |
             +---------+---------+
                       |
                       v
             +-------------------+
             | Optimization      |
             | History API       |
             +---------+---------+
                       |
                       v
             +-------------------+
             | Demand Forecast   |
             | Final Version     |
             +---------+---------+
                       |
                       v
             +-------------------+
             | Dashboard Final   |
             +---------+---------+
                       |
                       v
                  FULL TEST
                       |
                       v
              FRONTEND INTEGRATION
```

---

# Architecture Freeze

Once this plan is approved, do not change the core database/API architecture unless a new UI requirement or a genuine business-rule issue requires it.

The intended strategy is:

**Complete backend data contracts → complete backend tests → freeze API → integrate frontend.**

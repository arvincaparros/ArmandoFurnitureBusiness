# Furniture Optimization System — Implementation Plan

## 1. Project Overview

Build a web-based Furniture Production Optimization System with:

- React + TypeScript frontend
- FastAPI + Python backend
- PostgreSQL database
- SQLAlchemy ORM
- Alembic database migrations
- Google OR-Tools for Integer Linear Programming (ILP)
- Gemini API for AI-assisted demand forecasting and business insights
- Docker for local PostgreSQL development

The agreed system scope includes Login & Authentication, Dashboard, Resource Management, Product Data Management, Production Allocation, Resource Utilization Report, Transaction History, Optimization History, AI Demand Forecasting Chatbot, testing, deployment, and documentation.

---

## 2. Current Status

### Completed

- [x] Frontend UI development
- [x] Responsive frontend layout
- [x] Chatbot UI and responsive behavior
- [x] Backend project structure
- [x] Python virtual environment
- [x] FastAPI setup
- [x] PostgreSQL Docker container
- [x] SQLAlchemy dependency
- [x] `.env` configuration
- [x] FastAPI `/` endpoint
- [x] FastAPI `/health` endpoint
- [x] Backend-to-PostgreSQL connection verified

### Current Position

The project is ready to begin the database/model implementation.

---

# 3. Target Backend Structure

```text
backend/
│
├── app/
│   ├── __init__.py
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   └── models.py
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── dashboard.py
│   │   ├── resources.py
│   │   ├── products.py
│   │   ├── production.py
│   │   ├── reports.py
│   │   ├── transactions.py
│   │   ├── optimization.py
│   │   └── forecasting.py
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── resource.py
│   │   ├── product.py
│   │   ├── production.py
│   │   ├── transaction.py
│   │   ├── optimization.py
│   │   └── forecast.py
│   │
│   └── services/
│       ├── __init__.py
│       ├── auth.py
│       ├── dashboard.py
│       ├── production.py
│       ├── optimization.py
│       └── forecasting.py
│
├── alembic/
├── scripts/
│   └── import_excel.py
├── .env
├── .env.example
├── .gitignore
├── main.py
├── requirements.txt
└── docker-compose.yml
```

---

# 4. Source and Data Design Principles

The Excel workbook is the primary source for the operational data model.

The system requirements specify that resources are entered per production cycle, products contain material/labor/machine requirements, production allocation uses ILP to maximize profit, resource utilization compares used versus remaining resources, transaction history records actual production and sales, optimization history stores previous ILP runs, and demand forecasting analyzes historical transaction data.

### Rules

1. Do not make every Excel worksheet a database table.
2. Normalize repeated/horizontal Excel structures into relational tables.
3. Preserve the business terminology used by the source data.
4. Do not store values that can safely be calculated dynamically.
5. Clearly distinguish:
   - Source-supported fields
   - Derived/calculated fields
   - Recommended application fields
6. Preserve historical information when resource prices or optimization results change.
7. Validate the final schema against the Excel data before creating the first migration.

---

# 5. Core Database Model

## 5.1 Users

Table:

```text
users
```

Purpose:

- Authentication
- Authorized access
- User ownership/auditing

Recommended fields:

```text
id
username
password_hash
full_name
is_active
created_at
updated_at
```

Passwords must never be stored as plain text.

---

## 5.2 Production Cycles

Table:

```text
production_cycles
```

Purpose:

Represent a weekly/production-cycle context because resource quantities and prices are entered per production cycle.

Recommended fields:

```text
id
cycle_date
start_date
end_date
status
created_at
updated_at
```

Possible statuses:

```text
OPEN
CLOSED
ARCHIVED
```

---

## 5.3 Resources

Table:

```text
resources
```

Purpose:

Master list of resources used by production.

Source-supported examples include:

- Wood
- Sandpaper
- Nails
- Wood Glue
- Epoxy
- Labor Hours
- Circular Saw
- Table Planer
- Hand Planer
- Doorknob/Hinge

Recommended fields:

```text
id
name
resource_type
unit
is_active
created_at
updated_at
```

---

## 5.4 Cycle Resources

Table:

```text
cycle_resources
```

Purpose:

Store the amount and price of a resource for a specific production cycle.

Recommended fields:

```text
id
production_cycle_id
resource_id
available_quantity
unit_price
total_budget
created_at
updated_at
```

Relationship:

```text
production_cycles 1 ─── * cycle_resources * ─── 1 resources
```

This allows resource prices and availability to change from one production cycle to another without modifying the resource master record.

---

## 5.5 Products

Table:

```text
products
```

Purpose:

Furniture product master data.

Source-supported product information includes furniture name and selling price.

Recommended fields:

```text
id
name
selling_price
is_active
created_at
updated_at
```

Do not store material requirements directly as many separate columns if they can be represented through a normalized product-resource relationship.

---

## 5.6 Product Resource Requirements

Table:

```text
product_resource_requirements
```

Purpose:

Define how much of each resource is required to produce one unit of a product.

Recommended fields:

```text
id
product_id
resource_id
quantity_required
```

Relationship:

```text
products 1 ─── * product_resource_requirements * ─── 1 resources
```

This table is a primary input to the ILP model.

Examples of source-supported requirements:

- Wood per unit
- Epoxy per unit
- Nails per unit
- Wood Glue per unit
- Sandpaper per unit
- Labor Hours per unit
- Circular Saw hours per unit
- Table Planer hours per unit
- Hand Planer hours per unit

---

# 6. Cost Calculation Design

The source requirements state that material, labor, and machine costs should be automatically computed from current resource prices.

The application should therefore calculate:

```text
resource requirement
×
current cycle resource price
=
resource cost
```

Then:

```text
material cost
+
labor cost
+
machine cost
=
total cost
```

Then:

```text
selling price
-
total cost
=
unit profit
```

Do not treat calculated values such as total cost and profit as independent master-data sources.

Where historical values are required for optimization history, store the relevant snapshot/result as part of the optimization run.

---

# 7. Production Allocation

Production Allocation is the core optimization module.

## Objective

Maximize total profit.

## Constraints

Total resource consumption must not exceed available resources.

## Implementation

Create:

```text
app/services/optimization.py
```

Main service:

```python
run_optimization()
```

Flow:

```text
Production Cycle
       ↓
Cycle Resources
       ↓
Products
       ↓
Product Resource Requirements
       ↓
Calculate Current Unit Profit
       ↓
Build OR-Tools ILP Model
       ↓
Add Resource Constraints
       ↓
Maximize Profit
       ↓
Solve
       ↓
Save Optimization Run
       ↓
Save Optimization Results
```

---

# 8. Optimization Runs

Table:

```text
optimization_runs
```

Purpose:

Store every ILP execution.

Recommended fields:

```text
id
production_cycle_id
started_at
completed_at
duration_ms
status
objective_value
total_profit
created_by
```

Possible statuses:

```text
PENDING
RUNNING
SUCCESS
FAILED
```

---

# 9. Optimization Results

Table:

```text
optimization_results
```

Purpose:

Store the recommended production quantity for each product from an optimization run.

Recommended fields:

```text
id
optimization_run_id
product_id
recommended_quantity
unit_profit
total_profit
```

Relationship:

```text
optimization_runs 1 ─── * optimization_results * ─── 1 products
```

This supports Optimization History and comparison between runs.

---

# 10. Resource Utilization

Do not create a permanent resource-utilization table initially.

Calculate utilization from:

```text
cycle_resources
+
optimization_results
+
product_resource_requirements
```

For each resource:

```text
used =
SUM(
    recommended_quantity
    ×
    quantity_required
)
```

Then:

```text
remaining =
available_quantity - used
```

And:

```text
utilization_percentage =
used / available_quantity × 100
```

Bottleneck resources are resources with the highest utilization or resources that constrain the optimization.

This supports the Resource Utilization Report.

---

# 11. Production Allocation / Actual Production

Table:

```text
production_allocations
```

Purpose:

Record actual production and compare it against recommended production.

Recommended fields:

```text
id
production_cycle_id
optimization_result_id
product_id
recommended_quantity
actual_quantity
started_at
completed_at
duration_minutes
status
```

Calculated:

```text
variance =
actual_quantity - recommended_quantity
```

This supports Transaction History and production-performance reporting.

---

# 12. Sales Transactions

Table:

```text
sales_transactions
```

Purpose:

Normalize historical sales data from the Excel workbook and support demand forecasting.

Recommended fields:

```text
id
product_id
transaction_date
quantity
unit_price
total_sales
unit_profit
total_profit
created_at
```

The Excel's horizontally repeated product/sales/profit sections should be normalized into one row per product/date transaction.

Do not keep the spreadsheet's horizontal layout in PostgreSQL.

---

# 13. Waste Records

Table:

```text
waste_records
```

Purpose:

Store recorded waste by resource and date.

Recommended fields:

```text
id
production_cycle_id
resource_id
waste_date
quantity
created_at
```

The Excel's separate waste columns should be normalized into rows.

---

# 14. Planning Schedules

Table:

```text
planning_schedules
```

Purpose:

Store production planning dates, times, and durations.

Recommended fields:

```text
id
production_cycle_id
scheduled_date
start_time
end_time
duration_minutes
created_at
```

Do not store values such as `"4 HOURS"` as strings when they represent a duration.

Prefer numeric duration or an interval-compatible database representation.

---

# 15. Demand Forecasting

Demand forecasting is based on historical transaction/sales data.

Flow:

```text
sales_transactions
       ↓
Historical Demand
       ↓
Forecasting Service
       ↓
Forecast Result
       ↓
Forecast UI
       ↓
Gemini Chatbot
```

## Forecast Runs

Table:

```text
forecast_runs
```

Recommended fields:

```text
id
started_at
completed_at
forecast_period
model_name
status
```

## Forecast Results

Table:

```text
forecast_results
```

Recommended fields:

```text
id
forecast_run_id
product_id
forecast_date
predicted_demand
confidence_level
```

---

# 16. AI Forecasting Chatbot

Endpoint:

```text
POST /forecast/chat
```

Flow:

```text
React Chatbot
       ↓
FastAPI
       ↓
Forecasting Service
       ↓
Business Data Summary
       ↓
Gemini API
       ↓
AI Response
```

The chatbot should not directly access PostgreSQL.

The backend should retrieve and summarize relevant business information before sending context to Gemini.

Potential questions:

- Which furniture has the highest predicted demand?
- Which resource is currently the bottleneck?
- Why did the optimizer recommend this production mix?
- Which products should be prioritized?
- How does forecasted demand compare with the previous period?

---

# 17. Dashboard

Endpoint:

```text
GET /dashboard
```

Dashboard should aggregate:

- Current production cycle
- Available resources
- Last recommended production quantities
- Projected total profit
- Resource utilization
- Bottleneck resources
- Forecast summary where applicable

Example response:

```json
{
  "currentCycle": {},
  "availableResources": [],
  "recommendedProduction": [],
  "projectedProfit": 0,
  "resourceUtilization": [],
  "bottlenecks": []
}
```

Keep dashboard calculations in backend services rather than duplicating business calculations in React.

---

# 18. API Plan

## Authentication

```text
POST /auth/login
POST /auth/logout
GET  /auth/me
```

## Dashboard

```text
GET /dashboard
```

## Products

```text
GET    /products
POST   /products
GET    /products/{id}
PUT    /products/{id}
DELETE /products/{id}
```

## Resources

```text
GET    /resources
POST   /resources
GET    /resources/{id}
PUT    /resources/{id}
DELETE /resources/{id}
```

## Production

```text
GET  /production/cycles
POST /production/cycles
GET  /production/cycles/{id}
POST /production/allocate
GET  /production/allocations
```

## Transactions

```text
GET  /transactions
POST /transactions
GET  /transactions/{id}
```

## Optimization

```text
POST /optimization/run
GET  /optimization/history
GET  /optimization/{id}
```

## Reports

```text
GET /reports/resource-utilization
GET /reports/production
GET /reports/profit
```

## Forecasting

```text
POST /forecast/run
GET  /forecast
GET  /forecast/chart
POST /forecast/chat
```

---

# 19. Backend Layering

Use this architecture consistently:

```text
Router
   ↓
Schema validation
   ↓
Service
   ↓
SQLAlchemy model / repository operations
   ↓
PostgreSQL
```

Do not put optimization, cost calculations, forecasting, or complex business logic directly inside router functions.

---

# 20. Database Implementation Order

Implement database models in this order:

### Step 1 — Core master data

```text
User
Resource
Product
```

### Step 2 — Cycle-specific data

```text
ProductionCycle
CycleResource
```

### Step 3 — Product requirements

```text
ProductResourceRequirement
```

### Step 4 — Operational data

```text
SalesTransaction
ProductionAllocation
WasteRecord
PlanningSchedule
```

### Step 5 — Optimization

```text
OptimizationRun
OptimizationResult
```

### Step 6 — Forecasting

```text
ForecastRun
ForecastResult
```

Do not create the Alembic migration until the model relationships have been reviewed.

---

# 21. Alembic Plan

After the SQLAlchemy models are finalized:

```text
alembic init
       ↓
configure env.py
       ↓
connect SQLAlchemy metadata
       ↓
generate migration
       ↓
review migration
       ↓
alembic upgrade head
```

Never blindly trust autogenerated migrations. Review them before applying.

---

# 22. Excel Import Plan

Create:

```text
backend/scripts/import_excel.py
```

Import order:

```text
1. Products
2. Resources
3. Product Resource Requirements
4. Production Cycles
5. Cycle Resources
6. Sales Transactions
7. Waste Records
8. Planning Schedules
```

Before importing:

- Inspect worksheet names
- Inspect headers
- Inspect data types
- Identify formulas
- Identify blank rows
- Identify duplicated fields
- Normalize horizontal structures
- Map Excel terminology to database terminology
- Validate product/resource names

Do not import documentation/reference worksheets as operational records.

---

# 23. Frontend Integration Plan

Current frontend UI is already implemented.

Next transition:

```text
Current:

React
 ↓
Mock/static data
```

to:

```text
React
 ↓
API service
 ↓
FastAPI
 ↓
PostgreSQL
```

Create:

```text
src/api/
├── client.ts
├── dashboard.ts
├── products.ts
├── resources.ts
├── production.ts
├── transactions.ts
├── optimization.ts
└── forecasting.ts
```

Each UI module should handle:

```text
Loading
Success
Empty
Error
```

---

# 24. Testing Plan

## Backend

Test:

- Database connection
- Product CRUD
- Resource CRUD
- Production cycle creation
- Resource assignment
- Product resource requirements
- Cost calculations
- ILP constraints
- ILP objective
- Optimization history
- Transaction creation
- Forecast generation
- Dashboard aggregation

## Critical ILP validation

For every resource:

```text
total_consumption <= available_quantity
```

And:

```text
total_profit =
SUM(
    recommended_quantity × unit_profit
)
```

The optimizer must never recommend a production quantity that violates resource constraints.

---

# 25. Forecasting Validation

Before integrating Gemini:

```text
Historical Sales
      ↓
Forecast Algorithm
      ↓
Forecast Results
```

Validate:

- Product mapping
- Dates
- Missing values
- Historical quantities
- Forecast period
- Result consistency

Only after the numerical forecasting pipeline works should Gemini chatbot integration be added.

---

# 26. Deployment Plan

Development:

```text
React
localhost
   ↓
FastAPI
localhost:8000
   ↓
PostgreSQL Docker
localhost:5432
```

Production target:

```text
Frontend
   ↓
FastAPI
   ↓
PostgreSQL
   ↓
Gemini API
```

The project proposal recommends a dedicated office PC deployment because the system is intended for approximately 1–2 users, with internet connectivity required for Gemini requests.

---

# 27. Git Strategy

Use feature branches.

Example:

```text
develop
   │
   ├── feature/backend-database-models
   ├── feature/alembic-migrations
   ├── feature/product-api
   ├── feature/resource-api
   ├── feature/production-api
   ├── feature/optimization
   ├── feature/transactions
   ├── feature/forecasting
   ├── feature/authentication
   └── feature/frontend-api-integration
```

Recommended commit style:

```text
feat: add core database models
feat: add alembic initial migration
feat: add product management API
feat: add resource management API
feat: implement production optimization
feat: add optimization history
feat: add demand forecasting
feat: integrate forecasting chatbot
```

---

# 28. Milestones

| # | Milestone | Status |
|---|---|---|
| 1 | Frontend UI | DONE |
| 2 | Backend structure | DONE |
| 3 | Python environment | DONE |
| 4 | Docker PostgreSQL | DONE |
| 5 | FastAPI database connection | DONE |
| 6 | Final database model | NEXT |
| 7 | Alembic configuration | Pending |
| 8 | Initial database migration | Pending |
| 9 | Product API | Pending |
| 10 | Resource API | Pending |
| 11 | Production Cycle API | Pending |
| 12 | Cost Calculation | Pending |
| 13 | ILP Optimization | Pending |
| 14 | Resource Utilization | Pending |
| 15 | Transaction History | Pending |
| 16 | Optimization History | Pending |
| 17 | Demand Forecasting | Pending |
| 18 | AI Chatbot | Pending |
| 19 | Dashboard API | Pending |
| 20 | Authentication | Pending |
| 21 | Excel Data Import | Pending |
| 22 | Frontend API Integration | Pending |
| 23 | Automated Testing | Pending |
| 24 | Deployment | Pending |
| 25 | Documentation / Turnover | Pending |

---

# 29. Immediate Next Task

Do **not** start all APIs yet.

The next implementation task is:

```text
feature/backend-database-models
```

Implement and review these five core models first:

```text
Product
Resource
ProductionCycle
CycleResource
ProductResourceRequirement
```

Then verify:

```text
Product
   │
   └── ProductResourceRequirement
              │
              └── Resource

ProductionCycle
   │
   └── CycleResource
              │
              └── Resource
```

After those are correct:

```text
SQLAlchemy Models
        ↓
Alembic
        ↓
Initial Migration
        ↓
PostgreSQL
        ↓
CRUD APIs
```

This prevents us from building the API on top of a database structure that later needs to be redesigned.

---

# 30. Definition of Done

The system will be considered functionally complete when:

- [ ] User can log in/out
- [ ] User can manage products
- [ ] User can manage resources
- [ ] User can create/manage production cycles
- [ ] User can enter resource quantities and prices
- [ ] Product resource requirements are stored
- [ ] Product costs are calculated from current resource prices
- [ ] ILP optimization maximizes profit
- [ ] Resource constraints are enforced
- [ ] Recommended production quantities are saved
- [ ] Actual production can be recorded
- [ ] Sales transactions can be recorded
- [ ] Transaction history is available
- [ ] Optimization history is available
- [ ] Resource utilization is calculated
- [ ] Bottleneck resources are identified
- [ ] Historical sales data is available for forecasting
- [ ] Demand forecasting works
- [ ] Forecast results are displayed
- [ ] Forecast chatbot provides business insights
- [ ] Dashboard displays current production information
- [ ] Excel source data is migrated/validated
- [ ] Backend APIs have error handling
- [ ] Critical business logic is tested
- [ ] Frontend is connected to real APIs
- [ ] Production deployment is documented
- [ ] User documentation is prepared

---

## Final Development Sequence

```text
FRONTEND UI
    ✅
    │
    ▼
FASTAPI FOUNDATION
    ✅
    │
    ▼
POSTGRESQL + DOCKER
    ✅
    │
    ▼
DATABASE MODELS
    ← NEXT
    │
    ▼
ALEMBIC MIGRATION
    │
    ▼
PRODUCT API
    │
    ▼
RESOURCE + PRODUCTION CYCLE API
    │
    ▼
COST CALCULATION
    │
    ▼
ILP OPTIMIZATION
    │
    ▼
RESOURCE UTILIZATION
    │
    ▼
TRANSACTIONS
    │
    ▼
OPTIMIZATION HISTORY
    │
    ▼
DEMAND FORECASTING
    │
    ▼
GEMINI CHATBOT
    │
    ▼
DASHBOARD API
    │
    ▼
AUTHENTICATION
    │
    ▼
EXCEL DATA IMPORT
    │
    ▼
FRONTEND API INTEGRATION
    │
    ▼
TESTING
    │
    ▼
DEPLOYMENT
    │
    ▼
DOCUMENTATION / TURNOVER
```

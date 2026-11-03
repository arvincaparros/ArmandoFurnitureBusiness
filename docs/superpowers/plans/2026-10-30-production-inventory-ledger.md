# Production Application Ledger, Opening Inventory & Stock-Based Sales Validation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make "Apply to Production" an append-only, non-overwriting event that adds produced units to a derivable finished-goods stock figure, auto-fills Transaction History's Quantity Produced, and rejects sales exceeding available stock — while preserving unsold stock across 7-day cycles and leaving the ILP, `ProductionAllocation`, and historical forecast numbers untouched.

**Architecture:** `ProductionAllocation` stays exactly what it is today — the *current committed plan* for a cycle, still replaced wholesale on each apply, still the input to resource feasibility/consumption/financials. Alongside it, a new append-only ledger (`production_applications` → `production_application_items` + `production_application_resource_items`) records every apply event, its per-product produced quantities, and the raw-material capacity it consumed. A reviewed `opening_inventory_sets`/`opening_inventory_items` pair supplies auditable starting balances. Available stock is never stored: it is derived as `opening + Σ ledger produced − Σ sales sold` across all cycles. Cycle-scoped produced/sold totals come from cycle-filtered queries over the same two sources, so a new cycle resets those totals without touching stock.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 (`Mapped`/`mapped_column`) + Alembic + pytest + PostgreSQL on `127.0.0.1:5433` (`armando_furniture` dev / `armando_furniture_test` tests); React 19 + TanStack Query v5 + Mantine v9 + vitest + React Testing Library; Playwright (newly introduced in Task 17).

**Spec:** Conversation-provided spec "Product Allocation – Automatic Production Quantity and Inventory Tracking" plus the approved business decisions and additional requirements in the follow-up message. Both are reproduced inline in the task that implements them. The preceding investigation report is the factual baseline this plan argues from.

**Revision R1 (2026-10-30) — production forecast source.** The forecast's produced figure is no
longer taken from `SalesTransaction.quantity_produced`. `production_application_items` is now the
authoritative source for new production and `SalesTransaction.quantity` stays the authoritative
source for sales, so production appears on the chart with no sale recorded, several sales cannot
duplicate one applied batch, opening inventory is never counted as production, and a previous
cycle's production stays on its own date. `quantity_produced` is **retained** and still auto-filled
by the Task 10 drawdown — it keeps driving per-transaction production cost and stays the produced
figure for pre-rollout rows — but it is no longer the forecast's source of truth. What changed:
Global Constraints, the Key derivation rules, Task 11 Step 3/Step 5, Deliverable 5 (rewritten),
the dependency graph and checkpoints, the acceptance criteria, and four new tasks (19-22). Tasks
0-10 and 12-17 are unchanged.

## Global Constraints

- **NEVER run tests against `armando_furniture`.** Every write-enabled test run must resolve `DATABASE_URL` to `postgresql://...@127.0.0.1:5433/armando_furniture_test`. Task 0 is a hard prerequisite for every other task; do not start Task 1 until Task 0's verification step has printed the test database name.
- Do not change the ILP mathematical formulation: `create_decision_variables`, `add_resource_constraints`, `add_profit_objective`, `add_forecast_constraints`, the five `_solve_stage*` functions, or any `validate_minimum_demand_*` function in `backend/app/services/optimization.py`.
- `ProductionAllocation` keeps its current meaning, columns, `UniqueConstraint("production_cycle_id", "product_id", name="uq_production_allocation")`, and delete-then-reinsert behaviour inside `apply_optimization`. It is **not** the production history.
- The production application ledger is the authoritative source for all *new* production history. Never derive new production history from `ProductionAllocation`.
- **(R1)** The Demand Forecasting chart's production series reads `production_application_items` and nothing else. It must never be derived from `ProductionAllocation`, from `SalesTransaction.quantity_produced` on a cycle-attributed row, or from `opening_inventory_items`.
- **(R1)** Only a successful `apply_optimization` may record finished-goods production. Manual allocation CRUD (`create_allocation`/`update_allocation`/`delete_allocation`) is planning: it writes `ProductionAllocation` rows only and must never touch the ledger or change available stock.
- Available stock is **derived on read, never stored**. Do not add a `stock_quantity` column to `products`.
- `SalesTransaction.quantity` (sold) semantics are unchanged — `backend/app/services/forecasting.py::get_monthly_historical_demand` reads it and its output must not change for existing rows.
- `SalesTransaction.quantity_produced` must never be set to available stock, and the sum of `quantity_produced` across a cycle must never exceed that cycle's applied production. Existing rows are never rewritten.
- **(R1)** `SalesTransaction.quantity_produced` is a **compatibility and costing column**, not a production source. It is still auto-filled by the Task 10 drawdown (it drives `calculate_transaction_values`' production cost and is displayed in Transaction History), and it is still the produced figure the chart shows for **pre-rollout rows only** — those with `production_cycle_id IS NULL`. No new feature may read it as the authoritative produced quantity.
- **(R1)** Pre-rollout forecast output is frozen. `production_cycle_id IS NULL` is the legacy marker; nothing may backfill it, and no code path may rewrite or re-attribute a legacy row's stored `quantity_produced`. `tests/test_forecast.py`, `test_forecast_aggregation.py`, `test_forecast_timeseries.py` and `test_forecast_history.py` must pass **unedited** at every step.
- **[AMENDED BY AMENDMENT A]** A sales transaction is **REFUSED (HTTP 409)** unless a **complete** `REVIEWED` opening inventory set exists — every saleable product carrying an **explicit** quantity, including an explicit `0`. A missing row is **not** zero. Stock validation, once active, is never bypassed. (Original rule, now rejected: "Stock-based sales validation is *disabled* until a `REVIEWED` opening inventory set exists" — that left a window in which true stock could go negative.)
- A sales transaction whose date falls in no production cycle is **rejected** (HTTP 400). Never silently assign it to the latest cycle.
- Quantity columns stay `Numeric(12, 4)`, currency `Numeric(12, 2)`, matching every existing column. All Decimal values cross the API as JSON strings.
- Every new validation path must turn `ValueError`/`IntegrityError` into a clean 4xx — never a raw 500.
- No migration may be run against any database other than local dev (`armando_furniture`) and test (`armando_furniture_test`), and only after the user approves that step.
- **[AMENDED BY AMENDMENT D]** Do not stage, commit, push, merge, or deploy **at all**. Every task's Commit step is a prepared message only; `git add`/`git commit` must not be run. Each commit, push, deployment, and dev-database migration needs the user's separate explicit approval at the moment it is needed. `git add .`/`git add -A` remain forbidden.
- Preserve the existing untracked directories `.qoder/`, `backend/scripts/`, `backups/`, `docs/`, `frontend/design-reference/`. Do not touch files under them except this plan file and files a task explicitly names.
- Backend style: two blank lines between top-level defs, trailing commas in multi-line calls, docstrings explaining *why* (match `backend/app/services/allocation.py`). Frontend style: no semicolons, single quotes, default export at the bottom.

---

# PLAN AMENDMENTS — post-G1.6, pre-G2 (AUTHORITATIVE)

**These amendments were approved by the user after G1.5/G1.6 and OVERRIDE any conflicting inline
text later in this document, including code blocks.** Where an amendment supersedes a passage, the
passage is marked `[SUPERSEDED BY AMENDMENT x]` in place. An executor who finds a conflict follows
the amendment, not the original task text, and reports the conflict rather than guessing.

Why these exist: Decisions A-E below were taken after Tasks 0-3 had already shipped and after the
G1.5 FK corrections changed the schema's delete semantics. Several task bodies were written before
those facts existed and are now wrong in ways a literal executor would not notice.

## AMENDMENT A — Sales require a COMPLETE reviewed opening inventory (replaces the soft gate)

**User's requirement, verbatim in intent:** negative finished-goods stock must never be allowed. The
requirement is *unconditional*.

The original plan made stock validation **opt-in**: it stayed off until a `REVIEWED` set existed, and
sales were accepted unvalidated until then (old Global Constraint line 38; Task 10's
`test_stock_validation_is_skipped_before_opening_review`). That is now **rejected**. It left a window
in which true stock could go negative, which the `max(0, ...)` floor in Task 9 would then display as
`0` — hiding the deficit rather than preventing it.

**New rule:**

1. A sales transaction is **REFUSED** (HTTP 409) unless a **complete** `REVIEWED`
   `OpeningInventorySet` exists. Sales are blocked during setup, not accepted unvalidated.
2. **Complete** means every saleable product has an **explicit** `OpeningInventoryItem` row in that
   set — including an explicit `0`. A missing row is **not** zero; it is an incomplete declaration.
3. `review_opening_inventory_set` must **refuse to review** an incomplete set (HTTP 400, naming the
   products with no declared quantity), so a `REVIEWED` set is complete **by construction** and the
   sale path only has to ask "does a reviewed set exist".
4. Once stock validation is active it is **never** bypassed: no flag, no env var, no "skip if empty"
   branch. Every create/update path validates.

**Consequences that are NOT optional:**

- `is_stock_validation_enabled` keeps its name and signature but inverts its role: it is no longer a
  permission to validate, it is a precondition for selling at all. The sale path raises when it is
  `False` instead of skipping validation.
- `get_opening_quantities`' docstring claim that an empty dict "correctly resolves every product's
  opening balance to zero" is **void** under this amendment. An empty dict now means the set is
  incomplete, which cannot happen for a `REVIEWED` set once rule 3 is enforced.
- `OpeningInventoryItem`'s model docstring ("A product with no row here opens at zero - the absence
  is meaningful and deliberate") **contradicts this amendment** and must be corrected when Task 23
  runs. The docstring is currently shipped code; the amendment does not authorise editing it ahead
  of Task 23.
- This changes code that **already shipped in G1** (Task 2's service + router, reviewed and
  accepted). It therefore needs its own task rather than being smuggled into Task 10 - see Task 23.

### A.1 — RULED BY THE USER (both recommendations accepted). No longer a blocker.

Both questions below were put to the user and both recommended readings were approved verbatim.
Task 23 is unblocked on this axis.

**RULING 1 — saleable product = `Product.is_active IS TRUE`.**
**RULING 2 — completeness is evaluated against products existing on the set's `effective_date`.**
Products created after the snapshot have zero opening stock *by construction*; their stock comes
from subsequent production applications minus sales. Products existing on the effective date must
carry an explicit opening quantity, including an explicit zero.

The original framing and reasoning are kept below for provenance:

**(i) What is a "saleable product"?** Recommended: `Product.is_active IS TRUE`. Rationale: product
deletion is a soft delete (`services/product.py`), so inactive products are retired and requiring an
opening declaration for them would block review forever on historical clutter.

**(ii) What happens to a product created AFTER the reviewed snapshot?** This is the sharp edge. Taken
literally, rule 2 means adding any new product immediately makes the reviewed set incomplete and
blocks **all** sales until someone reviews a new set — an operational trap.
Recommended: completeness is evaluated against products that existed **at the set's
`effective_date`** (`products.created_at <= effective_date`). A product created after the snapshot
legitimately has no pre-existing stock, so it opens at zero **by construction, not by silence** - its
stock derives purely from ledger production, which is exactly correct. Under this reading rule 2's
"never silently treat missing as zero" still holds for every product the snapshot was actually about.
If the user rejects this, the alternative is that every new product requires a fresh reviewed set
before it can be sold, which is defensible but operationally heavy and must be a conscious choice.

## AMENDMENT B — Scoped ledger cleanup (supersedes the blanket purge)

Approved design, replacing G1.6's blanket purge now that Task 6 makes `apply_optimization` a real
ledger writer (which falsifies the blanket purge's premise that every ledger row is test residue):

```python
def purge_ledger(db, *, cycle_ids=None, product_ids=None, all_rows=False):
```

- The **five-table FK deletion order is PRESERVED EXACTLY** and is not open to change:
  `production_application_resource_items` -> `production_application_items` ->
  `production_applications` -> `opening_inventory_items` -> `opening_inventory_sets`.
  Scoping is applied as a filter *within* that order, never by reordering it.
- `db.rollback()` stays as the first statement (the G1.6 fix). Not negotiable - it is what keeps a
  failed transaction from turning teardown into a confusing error that also leaks rows.
- `all_rows=True` is permitted **only** from explicitly designated clean-slate fixtures:
  `cleanup_applications`, `cleanup_opening_inventory`, and Task 22's guardrail fixture. Any other
  caller passing `all_rows=True` is a defect.
- **Row-owning fixtures clean only their own records.** `optimization_cycle` -> `cycle_ids=[cycle.id]`;
  `test_products` -> `product_ids=[...]`; `cleanup_test_data` -> the ids it is about to delete.
  Scope **by cycle** as the primary key: it matches the FK and is the natural unit of ownership. For
  `test_products`, resolve the affected applications by joining on its product ids and delete those
  applications **whole**, rather than stripping items out from under a surviving parent.
- **A sentinel regression test is mandatory**, not optional: insert a ledger row owned by no fixture,
  run the suite, assert it survives. Without it the scoping is aspirational. No such test exists today.
- **Fix R-A:** `_cleanup_cycle` in `tests/test_optimization_history_lifecycle.py` deletes
  `OptimizationRun` rows by cycle id (comment: "in FK order"). Once Task 6 writes a ledger row,
  `production_applications.optimization_run_id` - RESTRICT since G1.5 - blocks that delete with
  IntegrityError. It must call the scoped purge for its cycle first. The plan could not have
  anticipated this: the RESTRICT decision postdates it.

Implemented by **Task 24**, which must land before Task 6 writes its first ledger row.

## AMENDMENT C — Four stale fixture instructions corrected

G1.6 already moved `cleanup_applications` and `cleanup_opening_inventory` into `conftest.py`, behind
one shared `purge_ledger` helper with `db.rollback()` and six call sites. Four task instructions
still describe doing that move from scratch, and one supplies an **older, inferior** fixture body (no
`rollback`, no opening-inventory tables, no row-owning-fixture call sites). A literal executor would
overwrite the G1.6 helper and re-introduce the 30-error teardown regression recorded under Ruling 21.

| Where | Original instruction | Amended |
|---|---|---|
| Task 6 Step 1 | "copy the `cleanup_applications` fixture ... into `conftest.py` ... delete the local copy. Place it after `cleanup_test_data`" + a 3-table fixture body | **Already done in G1.6.** Do not re-add, move, or overwrite it. Use the existing `conftest.py` fixture as-is. |
| Task 8 Step 9 | "Move the `two_cycles` fixture ... into `conftest.py`" | Still valid - `two_cycles` was never moved. Must not disturb `purge_ledger`, the two cleanup fixtures, or their call sites. |
| Task 10 Step 1 | "Add the shared cycle fixture `transaction_cycle` to `conftest.py`" + "Add `SalesTransaction` to `conftest.py`'s model import block" | Still valid - neither exists yet. `transaction_cycle` must be **function-scoped** (as written) and its teardown must use the scoped purge, not a blanket one. |
| Task 10 Step 6 | "move `_apply_production` to `conftest.py` as a fixture-returning helper if both files need it" | Still valid, with one constraint: it writes ledger rows, so any fixture wrapping it must be function-scoped and scope-clean its own rows per Amendment B. |

In all four cases: **preserve the G1.6 rollback fix, the shared helper, the five-table FK order, and
(after Task 24) the scoped-cleanup behaviour.** No task may reintroduce a per-file purge.

## AMENDMENT D — Commit policy (supersedes every task's Commit step)

**No automatic commits.** Every commit, push, deployment, and development-database migration requires
the user's separate explicit approval, requested at the moment it is needed.

- Every task's `- [ ] **Step N: Commit**` block is **retained as the prepared commit message only**.
  An executor must NOT run `git add` or `git commit`. Prepare the message, report it, stop.
- Standing rule 5 under "Task groups and review checkpoints" ("Each task's own commit exists") is
  **void**; see its in-place replacement.
- Review packages are therefore working-tree diffs, not commit ranges (already the practice since
  Ruling 3).
- `git add .` and `git add -A` remain forbidden outright.

## AMENDMENT E — G2 task scope and the Task 6/7 dependency, resolved

**Confirmed:** `G2a = Task 4` executes **first and alone**; then `G2 = Tasks 5, 6, 7`.

The plan's self-review admits Task 6 Step 6 needs Task 7 Step 3's `consumption_override` keyword and
offers "either execution order". That ambiguity is **closed**. Task 7's Interfaces consume only
`get_cycle_consumed_by_resource` (Task 4) - nothing from Task 6 - so the dependency is strictly
one-directional once ordered correctly:

```
Task 4  (G2a)  ledger service          -> reviewed before G2 starts
  |
Task 24        scoped purge + sentinel + R-A fix   (Amendment B; before any ledger write)
  |
Task 5         incremental capacity offset
  |
Task 7         consumption_override kwarg          <- MUST precede Task 6
  |
Task 6         rewire apply_optimization           <- consumes Task 5 AND Task 7
```

**Tasks 6 and 7 must NOT run as independent parallel implementations.** Strictly sequential, Task 7
first. Running Task 6 first would have it call a keyword argument that does not yet exist.

## New tasks created by these amendments

- **Task 23 — Mandatory complete opening inventory gate** (Amendment A). Group **G2b**, gate G1,
  **blocks G4**. Amends already-shipped Task 2 code: completeness check at review time (400 naming
  undeclared products), inverted `is_stock_validation_enabled` role, corrected
  `OpeningInventoryItem`/`get_opening_quantities` docstrings, and the Task 10 sale path raising 409
  when no complete reviewed set exists. Task 10's
  `test_stock_validation_is_skipped_before_opening_review` is **inverted** by this task: the same
  scenario must now assert the sale is refused. Completeness is evaluated over products with
  `is_active IS TRUE` and `created_at <= effective_date` per the A.1 ruling. **A.1 is RULED.**
- **Task 24 — Scoped ledger cleanup** (Amendment B). Group **G2a**, executes after Task 4 and
  **before Task 6**. Signature change, scoped call sites, mandatory sentinel test, and the R-A fix in
  `test_optimization_history_lifecycle.py`.

Both are test-and-service changes only. Neither adds a migration; the Alembic head stays
`93076b221d5d` until Task 8.

---

## Reference: canonical interfaces introduced by this plan

Names here are final — do not rename them in a later task.

**`backend/app/services/opening_inventory.py`**
```
OPENING_INVENTORY_DRAFT = "DRAFT"
OPENING_INVENTORY_REVIEWED = "REVIEWED"
OPENING_INVENTORY_SUPERSEDED = "SUPERSEDED"

generate_opening_inventory_number(db) -> str                        # "OI-0001"
get_opening_inventory_sets(db) -> list[OpeningInventorySet]
get_opening_inventory_set(db, set_id) -> OpeningInventorySet | None
get_reviewed_opening_inventory_set(db) -> OpeningInventorySet | None
is_stock_validation_enabled(db) -> bool
get_opening_quantities(db) -> dict[int, Decimal]                     # product_id -> qty
create_opening_inventory_set(db, data, user) -> OpeningInventorySet
update_opening_inventory_set(db, inventory_set, data) -> OpeningInventorySet
review_opening_inventory_set(db, inventory_set, user) -> OpeningInventorySet
```

**`backend/app/services/production_application.py`**
```
generate_application_number(db) -> str                              # "PA-0001"
has_application_for_run(db, optimization_run_id) -> bool
save_production_application(db, cycle_id, optimization_run_id,
                            produced_by_product_id,
                            consumed_resources) -> ProductionApplication   # no commit
get_cycle_consumed_by_resource(db, cycle_id) -> dict[int, Decimal]
get_cycle_produced_by_product(db, cycle_id) -> dict[int, Decimal]
get_total_produced_by_product(db) -> dict[int, Decimal]
get_applications(db, cycle_id=None) -> list[ProductionApplication]
```

**`backend/app/services/forecasting.py` (R1 additions)**
```
POINT_TYPE_SALE = "SALE"
POINT_TYPE_PRODUCTION = "PRODUCTION"
POINT_TYPE_FORECAST = "FORECAST"

get_production_event_series(db) -> dict[int, list[dict]]
    # product_id -> [{period, application_id, application_number,
    #                 production_cycle_id, quantity_produced}]

get_transaction_historical_demand(db) -> dict[int, list[dict]]
    # unchanged signature; "quantity_produced" is now Decimal | None -
    # the stored value for legacy rows (production_cycle_id IS NULL),
    # None for every cycle-attributed row
```

**`backend/app/services/inventory.py`**
```
lock_product_for_stock_update(db, product_id) -> None               # SELECT ... FOR UPDATE
get_total_sold_by_product(db) -> dict[int, Decimal]
get_cycle_sold_by_product(db, cycle_id) -> dict[int, Decimal]
get_available_stock(db) -> dict[int, Decimal]
get_available_stock_for_product(db, product_id) -> Decimal
get_unattributed_produced(db, cycle_id, product_id) -> Decimal
get_inventory_overview(db) -> dict
```

**`backend/app/services/transaction.py` (addition)**
```
resolve_production_cycle_for_date(db, transaction_date) -> ProductionCycle   # raises ValueError
```

**Changed signatures (backward-compatible, new params default to `None`)**
```
production_calculation.find_resource_capacity_shortages(
    db, cycle_id, quantities_by_product_id,
    requirement_override=None, already_consumed_by_resource_id=None) -> list[dict]

resource_utilization.calculate_resource_utilization(
    db, cycle_id, consumption_override=None) -> dict
```

**New endpoints**
```
GET   /api/opening-inventory                          -> list[OpeningInventorySetResponse]
GET   /api/opening-inventory/active                   -> OpeningInventoryStatusResponse
POST  /api/opening-inventory                          -> OpeningInventorySetResponse (201)
PATCH /api/opening-inventory/{set_id}                 -> OpeningInventorySetResponse
POST  /api/opening-inventory/{set_id}/review          -> OpeningInventorySetResponse
GET   /api/inventory                                  -> InventoryOverviewResponse
GET   /api/production-cycles/{cycle_id}/applications  -> list[ProductionApplicationResponse]
```

---

## Key derivation rules (the whole feature in six formulas)

```
opening(p)            = quantity from the single REVIEWED OpeningInventorySet, else 0
total_produced(p)     = Σ production_application_items.quantity_produced   (all cycles)
total_sold(p)         = Σ sales_transactions.quantity                      (all time)
available_stock(p)    = opening(p) + total_produced(p) − total_sold(p)

cycle_produced(p, c)  = Σ items.quantity_produced WHERE application.production_cycle_id = c
cycle_sold(p, c)      = Σ sales_transactions.quantity WHERE production_cycle_id = c

unattributed(p, c)    = cycle_produced(p, c) − Σ sales_transactions.quantity_produced
                                               WHERE production_cycle_id = c AND product_id = p
```

`unattributed` is what a new transaction's `quantity_produced` is auto-filled with. It is a
**drawdown**: the first sale after an apply carries the newly applied units, later sales in the
same cycle carry `0`. This guarantees `Σ quantity_produced over a cycle == cycle_produced`, so the
column can never overstate production, and available stock is never used as the produced figure.

**(R1) The chart's two historical series are read from two different tables, never from each
other:**
```
sales series(p)      = one SALE point per sales_transactions row
                       value plotted = quantity (sold)

production series(p) = one PRODUCTION point per production_application_items row
                       value plotted = quantity_produced
                       dated         = date(production_applications.applied_at)

legacy produced(p)   = sales_transactions.quantity_produced
                       WHERE production_cycle_id IS NULL      (tooltip only, as today)
```
Each apply is one row, so the production series is immune to how many sales exist (none, one or
ten), never includes opening inventory (a different table), and keeps a previous cycle's apply on
its own date instead of re-counting it into the current cycle. `unattributed` and the drawdown
survive for costing and display only — **the forecast no longer reads them.**

Incremental raw-material capacity for a *new* application in cycle `c`:
```
effective_available(r) = CycleResource.available_quantity(r, c)
                         − get_cycle_consumed_by_resource(db, c)[r]
```

---

## Task 0 (PREREQUISITE): Isolated `armando_furniture_test` database

**Requirements covered:** "Include a separate prerequisite to configure and verify an isolated armando_furniture_test database before running any write-enabled tests. Never run tests against armando_furniture."

**Why this is first:** `backend/tests/conftest.py:6` imports `SessionLocal` from `app.database.connection`, which reads `DATABASE_URL` from `backend/.env` at import time — today that is `armando_furniture`, the development database. Every existing test writes to dev data. No other task may run until this is closed.

**Files:**
- Create: `backend/.env.test` (gitignored, never committed)
- Create: `backend/.env.test.example` (committed)
- Modify: `.gitignore` (add `backend/.env.test`)
- Modify: `backend/tests/conftest.py:1-20` (env resolution + hard guard, above all app imports)
- Create: `backend/docs/test-database-setup.md`

**Interfaces:**
- Consumes: nothing.
- Produces: a `_require_test_database` session-scoped autouse fixture, and the guarantee that `app.database.connection.engine.url.database == "armando_furniture_test"` during any test run.

- [ ] **Step 1: Create the test database (manual, user-run)**

Ask the user to run this themselves — it is a DDL operation against their local PostgreSQL and must not be automated:

```
! psql -h 127.0.0.1 -p 5433 -U <user> -c "CREATE DATABASE armando_furniture_test"
```

Expected: `CREATE DATABASE`. If it already exists, `psql` reports `already exists` — that is fine, continue.

- [ ] **Step 2: Add `backend/.env.test.example` (committed template)**

```
# Copy to backend/.env.test. Consumed ONLY by backend/tests/conftest.py,
# which refuses to run unless the database name is exactly
# armando_furniture_test. The application itself never reads this file.
TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5433/armando_furniture_test
```

- [ ] **Step 3: Create `backend/.env.test` with the real local credentials**

Copy `.env.test.example` and replace the user/password with the same credentials already present in `backend/.env`. Keep the database name exactly `armando_furniture_test`.

- [ ] **Step 4: Gitignore it**

In `.gitignore`, directly under the existing `backend/.env` line in the `# Environment` block:

```
backend/.env
backend/.env.test
frontend/.env
.env
```

- [ ] **Step 5: Add the env resolution + guard at the very top of `backend/tests/conftest.py`**

This must sit **above** `from main import app` and `from app.database.connection import SessionLocal`
(currently lines 5-6). `python-dotenv`'s `load_dotenv` does not override variables already in the
environment, and `app/database/connection.py` calls it at import time — so setting
`os.environ["DATABASE_URL"]` here wins, and the application's own `.env` can never leak in.

```python
import os
from pathlib import Path

from dotenv import load_dotenv


# --- Test database isolation -------------------------------------------
#
# MUST run before any `app.*` or `main` import below: connection.py
# reads DATABASE_URL at import time, so by the time SessionLocal exists
# the choice of database is already locked in. load_dotenv() inside
# connection.py will NOT override what we set here (override=False is
# its default), so backend/.env's development URL can never win.
#
# The name check is deliberately an exact-match allowlist rather than a
# "not the dev database" denylist: a typo'd database name must abort the
# run, not create a stray database or silently target something else.
_TEST_DATABASE_NAME = "armando_furniture_test"

load_dotenv(
    Path(__file__).resolve().parents[1] / ".env.test",
    override=True,
)

_TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

if not _TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL is not configured. Copy "
        "backend/.env.test.example to backend/.env.test and set it to "
        f"the {_TEST_DATABASE_NAME} database. Tests must never run "
        "against the development database."
    )

if not _TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?")[0] == (
    _TEST_DATABASE_NAME
):
    raise RuntimeError(
        f"TEST_DATABASE_URL must point at {_TEST_DATABASE_NAME}, got: "
        f"{_TEST_DATABASE_URL.rsplit('/', 1)[-1]}"
    )

os.environ["DATABASE_URL"] = _TEST_DATABASE_URL

import pytest  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from app.database.connection import SessionLocal, engine  # noqa: E402
```

Then delete the now-duplicated original `import pytest`, `from fastapi.testclient import TestClient`,
`from main import app`, and `from app.database.connection import SessionLocal` lines (originally
lines 1-6), keeping the remaining `datetime`/`Decimal`/models/`hash_password` imports where they are.

- [ ] **Step 6: Add the belt-and-braces runtime guard fixture**

Append after the imports in `backend/tests/conftest.py`:

```python
@pytest.fixture(scope="session", autouse=True)
def _require_test_database():
    """
    Second, independent check against the ENGINE that was actually
    built - not just the environment variable the guard above read.
    Catches the case where something imported app.database.connection
    before this module (e.g. a stray plugin or a `-p` hook), which
    would have bound the engine to the development database before our
    os.environ assignment could take effect.
    """

    actual = engine.url.database

    if actual != _TEST_DATABASE_NAME:
        pytest.exit(
            f"Refusing to run: the SQLAlchemy engine is bound to "
            f"'{actual}', not '{_TEST_DATABASE_NAME}'.",
            returncode=3,
        )

    yield
```

- [ ] **Step 7: Create the schema in the test database**

```bash
cd backend && TEST_DATABASE_URL="$(grep -h '^TEST_DATABASE_URL=' .env.test | cut -d= -f2-)" \
  DATABASE_URL="$TEST_DATABASE_URL" python -m alembic upgrade head
```

Expected: Alembic runs every migration from `5bf105d35a96` to head `c7a1e4d9f2b8` and prints no errors.
**Confirm with the user before running** — this is the plan's first DDL execution.

- [ ] **Step 8: Verify the isolation with a throwaway probe test**

Create `backend/tests/test_database_isolation.py`:

```python
from app.database.connection import engine


def test_tests_run_against_the_isolated_test_database():
    """
    Guards the guard: if this ever fails, every other test in the suite
    has been writing to the wrong database.
    """

    assert engine.url.database == "armando_furniture_test"
    assert engine.url.port == 5433
```

- [ ] **Step 9: Run it and confirm the database name**

```bash
cd backend && python -m pytest tests/test_database_isolation.py -v -s
```

Expected: PASS, and the printed database name is `armando_furniture_test`.

- [ ] **Step 10: Run the full existing suite against the test database**

```bash
cd backend && python -m pytest -q
```

Expected: the suite passes (or fails only on pre-existing failures — record any such baseline
failures in the commit message so later tasks can tell new breakage from old).

- [ ] **Step 11: Document it**

Create `backend/docs/test-database-setup.md`:

```markdown
# Test database setup

Tests run **only** against `armando_furniture_test`. `backend/tests/conftest.py`
sets `DATABASE_URL` from `TEST_DATABASE_URL` (read from `backend/.env.test`)
before importing the application, and aborts the run if the resolved database
name is not exactly `armando_furniture_test`.

## One-time setup

1. `psql -h 127.0.0.1 -p 5433 -U <user> -c "CREATE DATABASE armando_furniture_test"`
2. `cp backend/.env.test.example backend/.env.test` and fill in local credentials.
3. `cd backend && DATABASE_URL="<the test URL>" python -m alembic upgrade head`

## Running tests

`cd backend && python -m pytest`

No environment variables needed at the call site — `conftest.py` resolves them.

## After adding a migration

Re-run step 3 so the test database stays at head.

`backend/.env.test` is gitignored. Never point it at `armando_furniture`.
```

- [ ] **Step 12: Commit**

```bash
git add .gitignore backend/.env.test.example backend/tests/conftest.py \
        backend/tests/test_database_isolation.py backend/docs/test-database-setup.md
git commit -m "test: isolate the test suite in armando_furniture_test

Tests previously resolved DATABASE_URL from backend/.env and wrote to the
development database. conftest.py now sets DATABASE_URL from TEST_DATABASE_URL
before any application import and aborts unless the database is exactly
armando_furniture_test.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 1: Opening inventory models + migration

**Requirements covered:** "Include an opening_inventory table with auditable opening balances"; "Initial inventory: opening inventory. Do not start with zero or assume existing physical stock is zero"; "Require opening inventory setup to be completed and reviewed before enabling stock-based sales validation."

**Design note for the implementer:** a header/items pair (not a flat table) because the *review* step is what gates stock validation, and a review needs something to attach to — a status, a reviewer, a timestamp. Corrections never mutate a reviewed set: a new set is created and reviewed, which flips the old one to `SUPERSEDED`. That keeps the balance history auditable while still letting the figure be fixed. This mirrors the `ResourceUtilizationRun`/`ResourceUtilizationHistoryItem` and `OptimizationRun`/`OptimizationResult` parent-child idiom already used twice in `models.py`.

**Files:**
- Modify: `backend/app/database/models.py` (append two classes after `ResourceUtilizationHistoryItem`, at end of file)
- Create: `backend/alembic/versions/<rev>_add_opening_inventory.py`
- Test: `backend/tests/test_opening_inventory.py` (new)

**Interfaces:**
- Consumes: `Base` from `app.database.connection`; `Product`, `User` from this module.
- Produces: `OpeningInventorySet` (`id`, `set_number`, `status`, `effective_date`, `notes`, `created_at`, `created_by_user_id`, `reviewed_at`, `reviewed_by_user_id`, `items`) and `OpeningInventoryItem` (`id`, `opening_inventory_set_id`, `product_id`, `quantity`, `notes`, `inventory_set`, `product`).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_opening_inventory.py`:

```python
from datetime import datetime
from decimal import Decimal

import pytest

from sqlalchemy.exc import IntegrityError

from app.database.models import (
    OpeningInventoryItem,
    OpeningInventorySet,
)


@pytest.fixture
def cleanup_opening_inventory(db):
    db.query(OpeningInventoryItem).delete(synchronize_session=False)
    db.query(OpeningInventorySet).delete(synchronize_session=False)
    db.commit()

    yield

    db.query(OpeningInventoryItem).delete(synchronize_session=False)
    db.query(OpeningInventorySet).delete(synchronize_session=False)
    db.commit()


def test_opening_inventory_set_persists_with_items(
    db, cleanup_opening_inventory, test_products,
):
    inventory_set = OpeningInventorySet(
        set_number="OI-TEST01",
        status="DRAFT",
        effective_date=datetime(2026, 10, 30),
        notes="counted by hand",
    )

    db.add(inventory_set)
    db.flush()

    db.add(
        OpeningInventoryItem(
            opening_inventory_set_id=inventory_set.id,
            product_id=test_products[0].id,
            quantity=Decimal("12.0000"),
            notes="warehouse A",
        )
    )

    db.commit()
    db.refresh(inventory_set)

    assert inventory_set.status == "DRAFT"
    assert inventory_set.reviewed_at is None
    assert len(inventory_set.items) == 1
    assert inventory_set.items[0].quantity == Decimal("12.0000")


def test_only_one_reviewed_set_can_exist(
    db, cleanup_opening_inventory,
):
    """
    The partial unique index is what makes
    get_reviewed_opening_inventory_set's "the" in its name true - two
    reviewed sets would make opening balances ambiguous, and every
    stock figure in the system depends on there being exactly one.
    """

    db.add(
        OpeningInventorySet(
            set_number="OI-TEST02",
            status="REVIEWED",
            effective_date=datetime(2026, 10, 30),
            reviewed_at=datetime(2026, 10, 30),
        )
    )
    db.commit()

    db.add(
        OpeningInventorySet(
            set_number="OI-TEST03",
            status="REVIEWED",
            effective_date=datetime(2026, 10, 31),
            reviewed_at=datetime(2026, 10, 31),
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_one_item_per_product_per_set(
    db, cleanup_opening_inventory, test_products,
):
    inventory_set = OpeningInventorySet(
        set_number="OI-TEST04",
        status="DRAFT",
        effective_date=datetime(2026, 10, 30),
    )

    db.add(inventory_set)
    db.flush()

    db.add_all(
        [
            OpeningInventoryItem(
                opening_inventory_set_id=inventory_set.id,
                product_id=test_products[0].id,
                quantity=Decimal("5.0000"),
            ),
            OpeningInventoryItem(
                opening_inventory_set_id=inventory_set.id,
                product_id=test_products[0].id,
                quantity=Decimal("7.0000"),
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd backend && python -m pytest tests/test_opening_inventory.py -v
```

Expected: collection error — `ImportError: cannot import name 'OpeningInventoryItem' from 'app.database.models'`.

- [ ] **Step 3: Add the models**

Append to the end of `backend/app/database/models.py`:

```python
class OpeningInventorySet(Base):
    """
    One auditable declaration of finished-goods stock on hand at the
    moment this system started tracking inventory. Exists because
    available stock is DERIVED (opening + applied production - sales)
    and the business already had physical stock when the ledger
    started - assuming zero would understate every product's stock
    forever.

    Lifecycle: DRAFT (editable) -> REVIEWED (frozen, authoritative) ->
    SUPERSEDED (a later set was reviewed in its place). A REVIEWED
    set's items are never mutated: a correction is a NEW set, so the
    original declared balance stays readable afterwards. At most one
    REVIEWED set exists at a time, enforced by the partial unique
    index below - every stock figure in the system depends on that.

    Stock-based sales validation is OFF until a REVIEWED set exists
    (see services/opening_inventory.py::is_stock_validation_enabled);
    sales recorded before then are accepted unvalidated rather than
    validated against a balance nobody has confirmed.
    """

    __tablename__ = "opening_inventory_sets"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    # Same sequential friendly-id convention as
    # SalesTransaction.transaction_number and
    # ResourceUtilizationRun.utilization_number - the service layer
    # generates "OI-0001"-style values; this default is only a
    # fallback for a row created outside that helper.
    set_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        index=True,
        default=lambda: f"OI-{uuid4().hex[:8].upper()}",
    )

    # "DRAFT" | "REVIEWED" | "SUPERSEDED" - see the constants in
    # app/services/opening_inventory.py, which are the only values
    # ever written.
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="DRAFT",
        index=True,
    )

    # The business date these balances were counted as of. Recorded
    # for the audit trail only - stock derivation never filters by it,
    # because the opening balance is by definition the starting point
    # for ALL ledger activity regardless of date.
    effective_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # SET NULL rather than CASCADE: deleting a user must never delete
    # the opening balance declaration that every stock figure depends
    # on. The audit trail degrades to "unknown user" instead.
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    items: Mapped[
        list["OpeningInventoryItem"]
    ] = relationship(
        back_populates="inventory_set",
        cascade="all, delete-orphan",
    )

    created_by: Mapped["User | None"] = relationship(
        foreign_keys=[created_by_user_id],
    )

    reviewed_by: Mapped["User | None"] = relationship(
        foreign_keys=[reviewed_by_user_id],
    )


class OpeningInventoryItem(Base):
    """
    One product's declared opening balance within a set. A product
    with no row here opens at zero - the absence is meaningful and
    deliberate (the user reviewed the set without declaring stock for
    it), which is why there is no backfill that invents rows for every
    product.
    """

    __tablename__ = "opening_inventory_items"

    __table_args__ = (
        UniqueConstraint(
            "opening_inventory_set_id",
            "product_id",
            name="uq_opening_inventory_item",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    opening_inventory_set_id: Mapped[int] = mapped_column(
        ForeignKey(
            "opening_inventory_sets.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    inventory_set: Mapped["OpeningInventorySet"] = relationship(
        back_populates="items",
    )

    product: Mapped["Product"] = relationship()
```

- [ ] **Step 4: Generate the migration**

```bash
cd backend && python -m alembic revision -m "add opening inventory"
```

Note the generated revision id. Confirm its `down_revision` is `c7a1e4d9f2b8` (the current single
head — verify with `python -m alembic heads`). Write the body by hand (this repo's migrations are
hand-written, not autogenerated):

```python
def upgrade() -> None:
    op.create_table(
        "opening_inventory_sets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("set_number", sa.String(length=20), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("effective_date", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("set_number"),
    )

    op.create_index(
        op.f("ix_opening_inventory_sets_id"),
        "opening_inventory_sets",
        ["id"],
    )

    op.create_index(
        op.f("ix_opening_inventory_sets_set_number"),
        "opening_inventory_sets",
        ["set_number"],
    )

    op.create_index(
        op.f("ix_opening_inventory_sets_status"),
        "opening_inventory_sets",
        ["status"],
    )

    # Partial unique index: at most ONE reviewed set may exist at a
    # time. Not expressible as a plain UniqueConstraint - DRAFT and
    # SUPERSEDED rows must be allowed to repeat freely.
    op.create_index(
        "uq_opening_inventory_single_reviewed",
        "opening_inventory_sets",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'REVIEWED'"),
    )

    op.create_table(
        "opening_inventory_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "opening_inventory_set_id", sa.Integer(), nullable=False,
        ),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(
            ["opening_inventory_set_id"],
            ["opening_inventory_sets.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "opening_inventory_set_id",
            "product_id",
            name="uq_opening_inventory_item",
        ),
    )

    op.create_index(
        op.f("ix_opening_inventory_items_id"),
        "opening_inventory_items",
        ["id"],
    )

    op.create_index(
        op.f("ix_opening_inventory_items_opening_inventory_set_id"),
        "opening_inventory_items",
        ["opening_inventory_set_id"],
    )

    op.create_index(
        op.f("ix_opening_inventory_items_product_id"),
        "opening_inventory_items",
        ["product_id"],
    )


def downgrade() -> None:
    op.drop_table("opening_inventory_items")
    op.drop_index(
        "uq_opening_inventory_single_reviewed",
        table_name="opening_inventory_sets",
    )
    op.drop_table("opening_inventory_sets")
```

- [ ] **Step 5: Apply the migration to the TEST database only**

```bash
cd backend && TEST_DATABASE_URL="$(grep -h '^TEST_DATABASE_URL=' .env.test | cut -d= -f2-)" \
  DATABASE_URL="$TEST_DATABASE_URL" python -m alembic upgrade head
```

Expected: the new revision runs. **Do not apply to `armando_furniture` yet** — dev migration happens
once, at the end, with the user's explicit approval (see Task 18).

- [ ] **Step 6: Run the test to verify it passes**

```bash
cd backend && python -m pytest tests/test_opening_inventory.py -v
```

Expected: 3 passed.

- [ ] **Step 7: Verify the rest of the suite is untouched**

```bash
cd backend && python -m pytest -q
```

Expected: same result as Task 0 Step 10.

- [ ] **Step 8: Commit**

```bash
git add backend/app/database/models.py backend/alembic/versions \
        backend/tests/test_opening_inventory.py
git commit -m "feat: add opening inventory set/item tables

Auditable declaration of finished-goods stock on hand before the
production ledger started. At most one REVIEWED set at a time
(partial unique index); corrections supersede rather than mutate.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 2: Opening inventory service, schemas, and API with the review gate

**Requirements covered:** "Include an opening_inventory table with auditable opening balances"; "Require opening inventory setup to be completed and reviewed before enabling stock-based sales validation."

**Files:**
- Create: `backend/app/services/opening_inventory.py`
- Create: `backend/app/schemas/opening_inventory.py`
- Create: `backend/app/routers/opening_inventory.py`
- Modify: `backend/main.py:10-21,60-71` (import + `include_router`)
- Test: `backend/tests/test_opening_inventory.py` (append)

**Interfaces:**
- Consumes: `OpeningInventorySet`, `OpeningInventoryItem` (Task 1); `get_current_user` from `app.services.auth`.
- Produces: every symbol listed under `services/opening_inventory.py` in the interface reference, plus `OpeningInventorySetResponse`, `OpeningInventoryStatusResponse`, `OpeningInventorySetCreate`, `OpeningInventorySetUpdate`, `OpeningInventoryItemInput`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_opening_inventory.py`:

```python
def test_create_draft_then_review_enables_stock_validation(
    client, db, cleanup_opening_inventory, test_products,
):
    """
    The review gate: is_stock_validation_enabled must stay False while
    the declaration is still a draft, and flip to True only once a
    human has reviewed it. Sales validation keys off this - validating
    against an unconfirmed balance would reject real sales.
    """

    from app.services.opening_inventory import (
        is_stock_validation_enabled,
    )

    assert is_stock_validation_enabled(db) is False

    create_response = client.post(
        "/api/opening-inventory",
        json={
            "effective_date": "2026-10-30T00:00:00",
            "notes": "initial physical count",
            "items": [
                {
                    "product_id": test_products[0].id,
                    "quantity": 8,
                    "notes": "warehouse A",
                }
            ],
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["status"] == "DRAFT"
    assert created["set_number"].startswith("OI-")
    assert len(created["items"]) == 1

    db.expire_all()
    assert is_stock_validation_enabled(db) is False

    review_response = client.post(
        f"/api/opening-inventory/{created['id']}/review",
    )

    assert review_response.status_code == 200
    reviewed = review_response.json()
    assert reviewed["status"] == "REVIEWED"
    assert reviewed["reviewed_at"] is not None
    assert reviewed["reviewed_by_username"] is not None

    db.expire_all()
    assert is_stock_validation_enabled(db) is True


def test_reviewed_set_cannot_be_edited(
    client, db, cleanup_opening_inventory, test_products,
):
    create_response = client.post(
        "/api/opening-inventory",
        json={
            "effective_date": "2026-10-30T00:00:00",
            "items": [
                {"product_id": test_products[0].id, "quantity": 8}
            ],
        },
    )

    set_id = create_response.json()["id"]
    client.post(f"/api/opening-inventory/{set_id}/review")

    update_response = client.patch(
        f"/api/opening-inventory/{set_id}",
        json={
            "items": [
                {"product_id": test_products[0].id, "quantity": 99}
            ]
        },
    )

    assert update_response.status_code == 400
    assert "reviewed" in update_response.json()["detail"].lower()


def test_reviewing_a_new_set_supersedes_the_previous_one(
    client, db, cleanup_opening_inventory, test_products,
):
    """
    A correction must not mutate the already-reviewed declaration -
    the original stays readable as SUPERSEDED, and the partial unique
    index means the flip and the new review happen together or not at
    all.
    """

    from app.services.opening_inventory import (
        get_opening_quantities,
    )

    first = client.post(
        "/api/opening-inventory",
        json={
            "effective_date": "2026-10-30T00:00:00",
            "items": [
                {"product_id": test_products[0].id, "quantity": 8}
            ],
        },
    ).json()

    client.post(f"/api/opening-inventory/{first['id']}/review")

    second = client.post(
        "/api/opening-inventory",
        json={
            "effective_date": "2026-10-31T00:00:00",
            "notes": "recount",
            "items": [
                {"product_id": test_products[0].id, "quantity": 11}
            ],
        },
    ).json()

    client.post(f"/api/opening-inventory/{second['id']}/review")

    db.expire_all()

    first_row = db.get(OpeningInventorySet, first["id"])
    second_row = db.get(OpeningInventorySet, second["id"])

    assert first_row.status == "SUPERSEDED"
    assert second_row.status == "REVIEWED"
    assert get_opening_quantities(db)[test_products[0].id] == (
        Decimal("11.0000")
    )


def test_opening_quantities_is_empty_before_review(
    db, cleanup_opening_inventory, test_products,
):
    """
    A DRAFT set's numbers must not leak into stock derivation - an
    unreviewed count is not an opening balance yet.
    """

    from app.services.opening_inventory import (
        get_opening_quantities,
    )

    inventory_set = OpeningInventorySet(
        set_number="OI-TEST05",
        status="DRAFT",
        effective_date=datetime(2026, 10, 30),
    )

    db.add(inventory_set)
    db.flush()

    db.add(
        OpeningInventoryItem(
            opening_inventory_set_id=inventory_set.id,
            product_id=test_products[0].id,
            quantity=Decimal("50.0000"),
        )
    )

    db.commit()

    assert get_opening_quantities(db) == {}


def test_create_rejects_duplicate_product_rows(
    client, cleanup_opening_inventory, test_products,
):
    response = client.post(
        "/api/opening-inventory",
        json={
            "effective_date": "2026-10-30T00:00:00",
            "items": [
                {"product_id": test_products[0].id, "quantity": 3},
                {"product_id": test_products[0].id, "quantity": 4},
            ],
        },
    )

    assert response.status_code == 422


def test_create_rejects_negative_quantity(
    client, cleanup_opening_inventory, test_products,
):
    response = client.post(
        "/api/opening-inventory",
        json={
            "effective_date": "2026-10-30T00:00:00",
            "items": [
                {"product_id": test_products[0].id, "quantity": -1}
            ],
        },
    )

    assert response.status_code == 422


def test_active_endpoint_reports_the_gate(
    client, cleanup_opening_inventory, test_products,
):
    before = client.get("/api/opening-inventory/active")

    assert before.status_code == 200
    assert before.json()["stock_validation_enabled"] is False
    assert before.json()["reviewed_set"] is None

    created = client.post(
        "/api/opening-inventory",
        json={
            "effective_date": "2026-10-30T00:00:00",
            "items": [
                {"product_id": test_products[0].id, "quantity": 8}
            ],
        },
    ).json()

    client.post(f"/api/opening-inventory/{created['id']}/review")

    after = client.get("/api/opening-inventory/active")

    assert after.json()["stock_validation_enabled"] is True
    assert after.json()["reviewed_set"]["id"] == created["id"]


def test_opening_inventory_requires_authentication(
    unauthenticated_client,
):
    assert unauthenticated_client.get(
        "/api/opening-inventory"
    ).status_code == 401
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_opening_inventory.py -v
```

Expected: the three original tests pass; the seven new ones fail with 404 (route not registered)
or `ModuleNotFoundError: app.services.opening_inventory`.

- [ ] **Step 3: Write the schemas**

Create `backend/app/schemas/opening_inventory.py`:

```python
from datetime import datetime
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)


class OpeningInventoryItemInput(BaseModel):
    product_id: int = Field(..., gt=0)

    # ge=0, not gt=0: declaring a product as explicitly zero is a real
    # and meaningful statement ("I counted, there are none"), distinct
    # from omitting it.
    quantity: Decimal = Field(
        ...,
        ge=0,
        decimal_places=4,
        max_digits=12,
    )

    notes: str | None = Field(default=None, max_length=500)


class OpeningInventoryItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: Decimal
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


def _require_unique_products(
    items: list[OpeningInventoryItemInput],
) -> list[OpeningInventoryItemInput]:
    """
    Rejected at the edge rather than left to the database's
    uq_opening_inventory_item constraint, so the caller gets a 422
    naming the problem instead of a 400 from an IntegrityError whose
    message exposes the constraint name.
    """

    product_ids = [item.product_id for item in items]

    if len(product_ids) != len(set(product_ids)):
        raise ValueError(
            "each product may appear at most once in an opening "
            "inventory set"
        )

    return items


class OpeningInventorySetCreate(BaseModel):
    effective_date: datetime
    notes: str | None = Field(default=None, max_length=500)
    items: list[OpeningInventoryItemInput] = Field(
        default_factory=list,
    )

    @model_validator(mode="after")
    def _validate_items(self):
        _require_unique_products(self.items)

        return self


class OpeningInventorySetUpdate(BaseModel):
    """
    DRAFT sets only - enforced in the service, not here, because the
    status lives on the row rather than in the request. `items`, when
    sent, REPLACES the whole item list: a partial per-item merge would
    make "remove this product's declared balance" inexpressible.
    """

    effective_date: datetime | None = None
    notes: str | None = Field(default=None, max_length=500)
    items: list[OpeningInventoryItemInput] | None = None

    @model_validator(mode="after")
    def _validate_items(self):
        if self.items is not None:
            _require_unique_products(self.items)

        return self


class OpeningInventorySetResponse(BaseModel):
    id: int
    set_number: str
    status: str
    effective_date: datetime
    notes: str | None
    created_at: datetime
    reviewed_at: datetime | None
    items: list[OpeningInventoryItemResponse]

    model_config = ConfigDict(from_attributes=True)

    # Usernames rather than raw ids: the audit trail is read by a
    # human, and the frontend has no user-lookup endpoint. None when
    # the user row was deleted (FK is ON DELETE SET NULL) or when the
    # action predates the column.
    @computed_field
    @property
    def created_by_username(self) -> str | None:
        return (
            self.created_by.username
            if getattr(self, "created_by", None)
            else None
        )

    @computed_field
    @property
    def reviewed_by_username(self) -> str | None:
        return (
            self.reviewed_by.username
            if getattr(self, "reviewed_by", None)
            else None
        )


class OpeningInventoryStatusResponse(BaseModel):
    """
    The single question every stock-aware screen needs answered before
    it can show or enforce anything: has opening inventory been
    reviewed yet, and if so, what does it say?
    """

    stock_validation_enabled: bool
    reviewed_set: OpeningInventorySetResponse | None
    draft_set: OpeningInventorySetResponse | None
```

**Implementer note:** `computed_field` reading `self.created_by` only works when the response is
built with `model_validate(orm_object, from_attributes=True)`. Pydantic v2 does not copy
un-declared ORM attributes onto the model, so the `getattr` guards above will return `None`.
If the tests show `created_by_username` as `None` for a real user, replace the two
`computed_field` properties with explicit `created_by_username: str | None` fields and populate
them in the router via a small `_to_response(inventory_set)` helper that reads
`inventory_set.created_by.username`. Prefer whichever passes the assertion in Step 1's
`test_create_draft_then_review_enables_stock_validation`.

- [ ] **Step 4: Write the service**

Create `backend/app/services/opening_inventory.py`:

```python
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database.models import (
    OpeningInventoryItem,
    OpeningInventorySet,
    Product,
    User,
)
from app.schemas.opening_inventory import (
    OpeningInventorySetCreate,
    OpeningInventorySetUpdate,
)


# The only three values ever written to
# OpeningInventorySet.status. DRAFT is editable; REVIEWED is frozen
# and authoritative (at most one at a time, enforced by the
# uq_opening_inventory_single_reviewed partial index); SUPERSEDED is
# a previously-reviewed set that a later review replaced - kept, never
# deleted, so the declared-balance history stays auditable.
OPENING_INVENTORY_DRAFT = "DRAFT"
OPENING_INVENTORY_REVIEWED = "REVIEWED"
OPENING_INVENTORY_SUPERSEDED = "SUPERSEDED"


def generate_opening_inventory_number(db: Session) -> str:
    """
    "OI-0001", "OI-0002", ... - same sequential friendly-id convention
    as transaction.py::generate_transaction_number and
    resource_utilization_history.py::generate_utilization_number,
    rather than the model's random-hex fallback default.
    """

    last_id = db.scalar(
        select(func.max(OpeningInventorySet.id))
    )

    return f"OI-{(last_id or 0) + 1:04d}"


def get_opening_inventory_sets(
    db: Session,
) -> list[OpeningInventorySet]:
    statement = (
        select(OpeningInventorySet)
        .options(
            selectinload(OpeningInventorySet.items),
        )
        .order_by(
            OpeningInventorySet.created_at.desc(),
            OpeningInventorySet.id.desc(),
        )
    )

    return list(db.scalars(statement).all())


def get_opening_inventory_set(
    db: Session,
    set_id: int,
) -> OpeningInventorySet | None:
    return db.get(OpeningInventorySet, set_id)


def get_reviewed_opening_inventory_set(
    db: Session,
) -> OpeningInventorySet | None:
    """
    "The" reviewed set, singular, is guaranteed by the
    uq_opening_inventory_single_reviewed partial unique index - this
    never has to disambiguate between two.
    """

    statement = (
        select(OpeningInventorySet)
        .options(selectinload(OpeningInventorySet.items))
        .where(
            OpeningInventorySet.status
            == OPENING_INVENTORY_REVIEWED
        )
        .limit(1)
    )

    return db.scalar(statement)


def get_draft_opening_inventory_set(
    db: Session,
) -> OpeningInventorySet | None:
    statement = (
        select(OpeningInventorySet)
        .options(selectinload(OpeningInventorySet.items))
        .where(
            OpeningInventorySet.status == OPENING_INVENTORY_DRAFT
        )
        .order_by(
            OpeningInventorySet.created_at.desc(),
            OpeningInventorySet.id.desc(),
        )
        .limit(1)
    )

    return db.scalar(statement)


# [AMENDED BY AMENDMENT A - Task 23 inverts this function's ROLE.]
# The name and signature stay. What changes is the caller's reaction
# to False: the sale path must RAISE (409) instead of skipping
# validation. After Task 23 a REVIEWED set is COMPLETE by
# construction (review refuses an incomplete declaration), so "a
# reviewed set exists" is sufficient here. The docstring below
# describes the REJECTED soft-gate behaviour and is superseded.
def is_stock_validation_enabled(db: Session) -> bool:
    """
    The gate. Stock-based sales validation stays OFF until a human has
    reviewed an opening balance declaration - validating sales against
    a balance nobody confirmed would reject legitimate sales of stock
    the system does not know about yet.
    """

    return (
        db.scalar(
            select(func.count(OpeningInventorySet.id)).where(
                OpeningInventorySet.status
                == OPENING_INVENTORY_REVIEWED
            )
        )
        or 0
    ) > 0


def get_opening_quantities(db: Session) -> dict[int, Decimal]:
    """
    product_id -> declared opening balance, from the REVIEWED set
    only.

    [AMENDED BY AMENDMENT A] The original claim that an empty dict
    "correctly resolves every product's opening balance to zero" is
    VOID: a missing row is an INCOMPLETE declaration, not a zero.
    After Task 23, review refuses an incomplete set, so a REVIEWED
    set always carries an explicit row per saleable product.
    """

    reviewed_set = get_reviewed_opening_inventory_set(db)

    if reviewed_set is None:
        return {}

    return {
        item.product_id: item.quantity
        for item in reviewed_set.items
    }


def _replace_items(
    db: Session,
    inventory_set: OpeningInventorySet,
    items,
) -> None:
    db.query(OpeningInventoryItem).filter(
        OpeningInventoryItem.opening_inventory_set_id
        == inventory_set.id
    ).delete(synchronize_session=False)

    for item in items:
        product = db.get(Product, item.product_id)

        if product is None:
            raise ValueError(
                f"Product {item.product_id} not found"
            )

        db.add(
            OpeningInventoryItem(
                opening_inventory_set_id=inventory_set.id,
                product_id=item.product_id,
                quantity=item.quantity,
                notes=item.notes,
            )
        )


def create_opening_inventory_set(
    db: Session,
    data: OpeningInventorySetCreate,
    user: User,
) -> OpeningInventorySet:
    """
    Always created as DRAFT - there is no "create already reviewed"
    path, because the review is a deliberate second human action and
    the whole point of the gate.
    """

    existing_draft = get_draft_opening_inventory_set(db)

    if existing_draft is not None:
        raise ValueError(
            "A draft opening inventory set already exists "
            f"({existing_draft.set_number}). Edit or review it "
            "instead of creating another."
        )

    inventory_set = OpeningInventorySet(
        set_number=generate_opening_inventory_number(db),
        status=OPENING_INVENTORY_DRAFT,
        effective_date=data.effective_date,
        notes=data.notes,
        created_by_user_id=user.id,
    )

    try:
        db.add(inventory_set)
        db.flush()

        _replace_items(db, inventory_set, data.items)

        db.commit()
        db.refresh(inventory_set)

        return inventory_set

    except Exception:
        db.rollback()
        raise


def update_opening_inventory_set(
    db: Session,
    inventory_set: OpeningInventorySet,
    data: OpeningInventorySetUpdate,
) -> OpeningInventorySet:
    if inventory_set.status != OPENING_INVENTORY_DRAFT:
        raise ValueError(
            "This opening inventory set has already been reviewed "
            "and can no longer be edited. Create a new set to "
            "correct the balances."
        )

    update_data = data.model_dump(exclude_unset=True)

    if "effective_date" in update_data:
        inventory_set.effective_date = update_data[
            "effective_date"
        ]

    if "notes" in update_data:
        inventory_set.notes = update_data["notes"]

    try:
        if data.items is not None:
            _replace_items(db, inventory_set, data.items)

        db.commit()
        db.refresh(inventory_set)

        return inventory_set

    except Exception:
        db.rollback()
        raise


def review_opening_inventory_set(
    db: Session,
    inventory_set: OpeningInventorySet,
    user: User,
) -> OpeningInventorySet:
    """
    DRAFT -> REVIEWED, demoting any currently-reviewed set to
    SUPERSEDED in the SAME transaction. Both happen together or
    neither does: the uq_opening_inventory_single_reviewed partial
    index would reject the insert half of a split attempt anyway, so
    doing it in one transaction turns a potential IntegrityError into
    a correct outcome.
    """

    if inventory_set.status == OPENING_INVENTORY_REVIEWED:
        raise ValueError(
            "This opening inventory set has already been reviewed."
        )

    if inventory_set.status != OPENING_INVENTORY_DRAFT:
        raise ValueError(
            "Only a draft opening inventory set can be reviewed."
        )

    if not inventory_set.items:
        raise ValueError(
            "Declare at least one product's opening balance before "
            "reviewing this set."
        )

    previous = get_reviewed_opening_inventory_set(db)

    try:
        if previous is not None:
            previous.status = OPENING_INVENTORY_SUPERSEDED
            db.flush()

        inventory_set.status = OPENING_INVENTORY_REVIEWED
        inventory_set.reviewed_at = datetime.utcnow()
        inventory_set.reviewed_by_user_id = user.id

        db.commit()
        db.refresh(inventory_set)

        return inventory_set

    except Exception:
        db.rollback()
        raise
```

- [ ] **Step 5: Write the router**

Create `backend/app/routers/opening_inventory.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User
from app.schemas.opening_inventory import (
    OpeningInventorySetCreate,
    OpeningInventorySetResponse,
    OpeningInventorySetUpdate,
    OpeningInventoryStatusResponse,
)
from app.services.auth import get_current_user
from app.services.opening_inventory import (
    create_opening_inventory_set,
    get_draft_opening_inventory_set,
    get_opening_inventory_set,
    get_opening_inventory_sets,
    get_reviewed_opening_inventory_set,
    is_stock_validation_enabled,
    review_opening_inventory_set,
    update_opening_inventory_set,
)


router = APIRouter(
    prefix="/api/opening-inventory",
    tags=["Opening Inventory"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=list[OpeningInventorySetResponse],
    summary="List opening inventory sets",
)
def list_opening_inventory_sets(
    db: Session = Depends(get_db),
):
    return get_opening_inventory_sets(db)


# Registered before GET /{set_id} on purpose - FastAPI matches routes
# in registration order, and /{set_id}'s int path param would
# otherwise greedily match the literal "active" and fail as an invalid
# integer (422). Same reasoning as GET /api/production-cycles/latest.
@router.get(
    "/active",
    response_model=OpeningInventoryStatusResponse,
    summary="Opening inventory review status",
)
def get_opening_inventory_status(
    db: Session = Depends(get_db),
):
    return {
        "stock_validation_enabled": is_stock_validation_enabled(db),
        "reviewed_set": get_reviewed_opening_inventory_set(db),
        "draft_set": get_draft_opening_inventory_set(db),
    }


@router.get(
    "/{set_id}",
    response_model=OpeningInventorySetResponse,
)
def get_opening_inventory_set_by_id(
    set_id: int,
    db: Session = Depends(get_db),
):
    inventory_set = get_opening_inventory_set(db, set_id)

    if inventory_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opening inventory set not found",
        )

    return inventory_set


@router.post(
    "",
    response_model=OpeningInventorySetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_new_opening_inventory_set(
    data: OpeningInventorySetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return create_opening_inventory_set(db, data, current_user)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{set_id}",
    response_model=OpeningInventorySetResponse,
)
def update_existing_opening_inventory_set(
    set_id: int,
    data: OpeningInventorySetUpdate,
    db: Session = Depends(get_db),
):
    inventory_set = get_opening_inventory_set(db, set_id)

    if inventory_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opening inventory set not found",
        )

    try:
        return update_opening_inventory_set(
            db, inventory_set, data,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/{set_id}/review",
    response_model=OpeningInventorySetResponse,
    summary="Mark an opening inventory set as reviewed",
)
def review_existing_opening_inventory_set(
    set_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    inventory_set = get_opening_inventory_set(db, set_id)

    if inventory_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opening inventory set not found",
        )

    try:
        return review_opening_inventory_set(
            db, inventory_set, current_user,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
```

- [ ] **Step 6: Register the router**

In `backend/main.py`, add after the existing `resource_utilization` import (line 21):

```python
from app.routers.opening_inventory import router as opening_inventory_router
```

and after `app.include_router(resource_utilization_router)` (line 71):

```python
app.include_router(opening_inventory_router)
```

- [ ] **Step 7: Run the tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_opening_inventory.py -v
```

Expected: 10 passed.

- [ ] **Step 8: Verify the protected-endpoint audit still passes**

`backend/tests/test_business_endpoint_protection.py` enumerates routers and asserts every business
endpoint requires auth. The new router carries `dependencies=[Depends(get_current_user)]`, so it
should pass — but run it explicitly, since it may hard-code a route count:

```bash
cd backend && python -m pytest tests/test_business_endpoint_protection.py -v
```

Expected: PASS. If it asserts an exact endpoint count, update that count and note the change in the
commit message.

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/opening_inventory.py \
        backend/app/schemas/opening_inventory.py \
        backend/app/routers/opening_inventory.py \
        backend/main.py backend/tests/test_opening_inventory.py
git commit -m "feat: opening inventory API with a review gate

Stock-based sales validation stays disabled until a human reviews an
opening balance declaration. Corrections supersede rather than mutate.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 3: Production application ledger models + migration

**Requirements covered:** "Add an append-only production application ledger"; "Include a production_application_resource_items table to record resource consumption per application, so subsequent applications cannot reuse previously consumed capacity"; "Reject duplicate applications of the same optimization run"; "Use the production application ledger as the authoritative source for new production history."

**Design note:** three tables, not one. The header carries the apply event (cycle, which optimization run, when) and owns the `UNIQUE(optimization_run_id)` that makes duplicate application structurally impossible. Product items carry produced quantities (the stock input). Resource items carry consumed raw-material quantities (the incremental-capacity input) and denormalise `resource_name`/`unit` at write time for the same reason `ResourceUtilizationHistoryItem` does — a later rename or soft-delete must not change what an application recorded.

**Files:**
- Modify: `backend/app/database/models.py` (append three classes at end of file)
- Create: `backend/alembic/versions/<rev>_add_production_application_ledger.py`
- Test: `backend/tests/test_production_application.py` (new)

**Interfaces:**
- Consumes: `Base`, `Product`, `Resource`, `ProductionCycle`, `OptimizationRun`.
- Produces: `ProductionApplication` (`id`, `application_number`, `production_cycle_id`, `optimization_run_id`, `applied_at`, `product_items`, `resource_items`, `production_cycle`, `optimization_run`); `ProductionApplicationItem` (`id`, `production_application_id`, `product_id`, `quantity_produced`, `application`, `product`); `ProductionApplicationResourceItem` (`id`, `production_application_id`, `resource_id`, `resource_name`, `unit`, `consumed_quantity`, `application`).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_production_application.py`:

```python
from datetime import datetime
from decimal import Decimal

import pytest

from sqlalchemy.exc import IntegrityError

from app.database.models import (
    OptimizationRun,
    ProductionApplication,
    ProductionApplicationItem,
    ProductionApplicationResourceItem,
)


@pytest.fixture
def cleanup_applications(db):
    def _purge():
        db.query(ProductionApplicationResourceItem).delete(
            synchronize_session=False
        )
        db.query(ProductionApplicationItem).delete(
            synchronize_session=False
        )
        db.query(ProductionApplication).delete(
            synchronize_session=False
        )
        db.commit()

    _purge()

    yield

    _purge()


def _make_run(db, cycle_id):
    run = OptimizationRun(
        production_cycle_id=cycle_id,
        started_at=datetime(2026, 10, 30, 9, 0),
        completed_at=datetime(2026, 10, 30, 9, 0, 1),
        status="OPTIMAL",
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    return run


def test_application_persists_product_and_resource_items(
    db, cleanup_applications, optimization_cycle, test_products,
    test_resources,
):
    run = _make_run(db, optimization_cycle.id)

    application = ProductionApplication(
        application_number="PA-TEST01",
        production_cycle_id=optimization_cycle.id,
        optimization_run_id=run.id,
        applied_at=datetime(2026, 10, 30, 9, 5),
    )

    db.add(application)
    db.flush()

    db.add(
        ProductionApplicationItem(
            production_application_id=application.id,
            product_id=test_products[0].id,
            quantity_produced=Decimal("10.0000"),
        )
    )

    db.add(
        ProductionApplicationResourceItem(
            production_application_id=application.id,
            resource_id=test_resources[0].id,
            resource_name=test_resources[0].name,
            unit=test_resources[0].unit,
            consumed_quantity=Decimal("120.0000"),
        )
    )

    db.commit()
    db.refresh(application)

    assert len(application.product_items) == 1
    assert len(application.resource_items) == 1
    assert application.product_items[0].quantity_produced == (
        Decimal("10.0000")
    )
    assert application.resource_items[0].consumed_quantity == (
        Decimal("120.0000")
    )


def test_the_same_optimization_run_cannot_be_applied_twice(
    db, cleanup_applications, optimization_cycle,
):
    """
    The structural duplicate guard. Service-level checks can race;
    this constraint cannot - it is what makes "apply the same plan
    twice and get double the units" impossible rather than unlikely.
    """

    run = _make_run(db, optimization_cycle.id)

    db.add(
        ProductionApplication(
            application_number="PA-TEST02",
            production_cycle_id=optimization_cycle.id,
            optimization_run_id=run.id,
            applied_at=datetime(2026, 10, 30, 9, 5),
        )
    )
    db.commit()

    db.add(
        ProductionApplication(
            application_number="PA-TEST03",
            production_cycle_id=optimization_cycle.id,
            optimization_run_id=run.id,
            applied_at=datetime(2026, 10, 30, 9, 6),
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_two_applications_can_coexist_in_one_cycle(
    db, cleanup_applications, optimization_cycle, test_products,
):
    """
    The whole point of the ledger: the Day-1 and Day-5 applications in
    the spec's example must both survive. ProductionAllocation cannot
    express this (one row per product per cycle); this table can.
    """

    first_run = _make_run(db, optimization_cycle.id)
    second_run = _make_run(db, optimization_cycle.id)

    for index, run in enumerate((first_run, second_run), start=1):
        application = ProductionApplication(
            application_number=f"PA-TEST1{index}",
            production_cycle_id=optimization_cycle.id,
            optimization_run_id=run.id,
            applied_at=datetime(2026, 10, 30, 9, index),
        )

        db.add(application)
        db.flush()

        db.add(
            ProductionApplicationItem(
                production_application_id=application.id,
                product_id=test_products[0].id,
                quantity_produced=Decimal("10.0000"),
            )
        )

    db.commit()

    rows = (
        db.query(ProductionApplication)
        .filter(
            ProductionApplication.production_cycle_id
            == optimization_cycle.id
        )
        .all()
    )

    assert len(rows) == 2
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd backend && python -m pytest tests/test_production_application.py -v
```

Expected: `ImportError: cannot import name 'ProductionApplication'`.

- [ ] **Step 3: Add the models**

Append to the end of `backend/app/database/models.py`:

```python
class ProductionApplication(Base):
    """
    One "Apply to Production" event - APPEND-ONLY, and the
    authoritative source for all new production history.

    Deliberately NOT ProductionAllocation. That table is the CURRENT
    COMMITTED PLAN for a cycle: one row per product
    (uq_production_allocation), fully deleted and reinserted by
    apply_optimization on every apply, and read by resource
    feasibility/consumption/financials. Those semantics are correct
    for a plan and useless as a history - a second apply in the same
    cycle overwrites the first, so "10 units on Day 1 plus 10 more on
    Day 5" cannot be represented there at all. This table records
    every apply event instead, and nothing ever deletes or mutates a
    row.

    optimization_run_id is UNIQUE: applying the same optimization run
    twice would double-count its units into available stock. The
    service layer checks for it first and returns a clean 400 (see
    services/production_application.py::has_application_for_run), but
    the constraint is what makes it impossible under concurrency
    rather than merely unlikely.
    """

    __tablename__ = "production_applications"

    __table_args__ = (
        UniqueConstraint(
            "optimization_run_id",
            name="uq_production_application_run",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    application_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        index=True,
        default=lambda: f"PA-{uuid4().hex[:8].upper()}",
    )

    production_cycle_id: Mapped[int] = mapped_column(
        ForeignKey(
            "production_cycles.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    optimization_run_id: Mapped[int] = mapped_column(
        ForeignKey(
            "optimization_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    applied_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    production_cycle: Mapped["ProductionCycle"] = relationship()

    optimization_run: Mapped["OptimizationRun"] = relationship()

    product_items: Mapped[
        list["ProductionApplicationItem"]
    ] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
    )

    resource_items: Mapped[
        list["ProductionApplicationResourceItem"]
    ] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
    )


class ProductionApplicationItem(Base):
    """
    How many units of one product a single apply event produced. The
    sum of these across ALL cycles is the production half of available
    stock (see services/inventory.py::get_available_stock); the sum
    within one cycle is that cycle's produced total.
    """

    __tablename__ = "production_application_items"

    __table_args__ = (
        UniqueConstraint(
            "production_application_id",
            "product_id",
            name="uq_production_application_item",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    production_application_id: Mapped[int] = mapped_column(
        ForeignKey(
            "production_applications.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    quantity_produced: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    application: Mapped["ProductionApplication"] = relationship(
        back_populates="product_items",
    )

    product: Mapped["Product"] = relationship()


class ProductionApplicationResourceItem(Base):
    """
    How much of one resource a single apply event consumed. This is
    what makes consumption INCREMENTAL: the next application in the
    same cycle gets
    CycleResource.available_quantity minus the sum of these rows
    (see services/production_application.py::
    get_cycle_consumed_by_resource), so it can never re-spend capacity
    an earlier application already used.

    resource_name/unit are denormalised at write time, and resource_id
    is ON DELETE SET NULL - same reasoning as
    ResourceUtilizationHistoryItem: what an application consumed is a
    historical fact that must stay fully displayable even if the
    resource is later renamed or removed.
    """

    __tablename__ = "production_application_resource_items"

    __table_args__ = (
        UniqueConstraint(
            "production_application_id",
            "resource_id",
            name="uq_production_application_resource_item",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    production_application_id: Mapped[int] = mapped_column(
        ForeignKey(
            "production_applications.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    resource_id: Mapped[int | None] = mapped_column(
        ForeignKey("resources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    resource_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    unit: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    consumed_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    application: Mapped["ProductionApplication"] = relationship(
        back_populates="resource_items",
    )

    resource: Mapped["Resource | None"] = relationship()
```

- [ ] **Step 4: Write the migration**

```bash
cd backend && python -m alembic revision -m "add production application ledger"
```

`down_revision` must be Task 1's revision id (verify with `python -m alembic heads` — there must be
exactly one head). Body:

```python
def upgrade() -> None:
    op.create_table(
        "production_applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "application_number", sa.String(length=20), nullable=False,
        ),
        sa.Column("production_cycle_id", sa.Integer(), nullable=False),
        sa.Column("optimization_run_id", sa.Integer(), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["production_cycle_id"],
            ["production_cycles.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["optimization_run_id"],
            ["optimization_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_number"),
        sa.UniqueConstraint(
            "optimization_run_id",
            name="uq_production_application_run",
        ),
    )

    op.create_index(
        op.f("ix_production_applications_id"),
        "production_applications",
        ["id"],
    )

    op.create_index(
        op.f("ix_production_applications_application_number"),
        "production_applications",
        ["application_number"],
    )

    op.create_index(
        op.f("ix_production_applications_production_cycle_id"),
        "production_applications",
        ["production_cycle_id"],
    )

    op.create_index(
        op.f("ix_production_applications_optimization_run_id"),
        "production_applications",
        ["optimization_run_id"],
    )

    op.create_table(
        "production_application_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "production_application_id", sa.Integer(), nullable=False,
        ),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column(
            "quantity_produced", sa.Numeric(12, 4), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["production_application_id"],
            ["production_applications.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "production_application_id",
            "product_id",
            name="uq_production_application_item",
        ),
    )

    op.create_index(
        op.f("ix_production_application_items_id"),
        "production_application_items",
        ["id"],
    )

    op.create_index(
        op.f("ix_production_application_items_production_application_id"),
        "production_application_items",
        ["production_application_id"],
    )

    op.create_index(
        op.f("ix_production_application_items_product_id"),
        "production_application_items",
        ["product_id"],
    )

    op.create_table(
        "production_application_resource_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "production_application_id", sa.Integer(), nullable=False,
        ),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column(
            "resource_name", sa.String(length=100), nullable=False,
        ),
        sa.Column("unit", sa.String(length=30), nullable=False),
        sa.Column(
            "consumed_quantity", sa.Numeric(12, 4), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["production_application_id"],
            ["production_applications.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"], ["resources.id"], ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "production_application_id",
            "resource_id",
            name="uq_production_application_resource_item",
        ),
    )

    op.create_index(
        op.f("ix_production_application_resource_items_id"),
        "production_application_resource_items",
        ["id"],
    )

    op.create_index(
        op.f(
            "ix_production_application_resource_items_"
            "production_application_id"
        ),
        "production_application_resource_items",
        ["production_application_id"],
    )

    op.create_index(
        op.f("ix_production_application_resource_items_resource_id"),
        "production_application_resource_items",
        ["resource_id"],
    )


def downgrade() -> None:
    op.drop_table("production_application_resource_items")
    op.drop_table("production_application_items")
    op.drop_table("production_applications")
```

- [ ] **Step 5: Apply to the test database and run the test**

```bash
cd backend && TEST_DATABASE_URL="$(grep -h '^TEST_DATABASE_URL=' .env.test | cut -d= -f2-)" \
  DATABASE_URL="$TEST_DATABASE_URL" python -m alembic upgrade head \
  && python -m pytest tests/test_production_application.py -v
```

Expected: migration applies, 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/database/models.py backend/alembic/versions \
        backend/tests/test_production_application.py
git commit -m "feat: add append-only production application ledger

Three tables: the apply event (UNIQUE on optimization_run_id, so the
same plan can never be applied twice), its per-product produced
quantities, and its per-resource consumed quantities. ProductionAllocation
is untouched and remains the current committed plan.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 4: Production application service — write path and aggregate readers

**Requirements covered:** "Use the production application ledger as the authoritative source for new production history"; "Reject duplicate applications of the same optimization run"; "Preserve unsold stock across production cycles while resetting cycle-specific production and sales totals" (the produced half).

**Files:**
- Create: `backend/app/services/production_application.py`
- Create: `backend/app/schemas/production_application.py`
- Test: `backend/tests/test_production_application.py` (append)

**Interfaces:**
- Consumes: the three models from Task 3.
- Produces: every symbol under `services/production_application.py` in the interface reference, plus `ProductionApplicationResponse`, `ProductionApplicationItemResponse`, `ProductionApplicationResourceItemResponse`.

`save_production_application`'s two payload parameters have exactly these shapes — later tasks build them:

```python
produced_by_product_id: dict[int, Decimal]       # {product_id: units}
consumed_resources: list[dict]                   # [{"resource_id": int | None,
                                                 #   "resource_name": str,
                                                 #   "unit": str,
                                                 #   "consumed_quantity": Decimal}, ...]
```

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_production_application.py`:

```python
def test_save_production_application_does_not_commit(
    db, cleanup_applications, optimization_cycle, test_products,
    test_resources,
):
    """
    Must leave the transaction open so apply_optimization can commit
    the ledger, the ProductionAllocation rows, and the utilization
    snapshot together - exactly the contract
    save_resource_utilization_history already follows.
    """

    from app.services.production_application import (
        save_production_application,
    )

    run = _make_run(db, optimization_cycle.id)

    application = save_production_application(
        db,
        optimization_cycle.id,
        run.id,
        {test_products[0].id: Decimal("10")},
        [
            {
                "resource_id": test_resources[0].id,
                "resource_name": test_resources[0].name,
                "unit": test_resources[0].unit,
                "consumed_quantity": Decimal("120"),
            }
        ],
    )

    assert application.application_number.startswith("PA-")

    db.rollback()

    assert (
        db.query(ProductionApplication)
        .filter(
            ProductionApplication.production_cycle_id
            == optimization_cycle.id
        )
        .count()
        == 0
    )


def test_cycle_aggregates_sum_across_applications(
    db, cleanup_applications, optimization_cycle, test_products,
    test_resources,
):
    """
    The spec's Day-1-plus-Day-5 example, at the aggregate level: two
    applications of 10 must read back as 20 produced for the cycle,
    and their resource consumption must add up too - that sum is what
    stops the second application re-spending the first's capacity.
    """

    from app.services.production_application import (
        get_cycle_consumed_by_resource,
        get_cycle_produced_by_product,
        get_total_produced_by_product,
        save_production_application,
    )

    for _ in range(2):
        run = _make_run(db, optimization_cycle.id)

        save_production_application(
            db,
            optimization_cycle.id,
            run.id,
            {test_products[0].id: Decimal("10")},
            [
                {
                    "resource_id": test_resources[0].id,
                    "resource_name": test_resources[0].name,
                    "unit": test_resources[0].unit,
                    "consumed_quantity": Decimal("120"),
                }
            ],
        )

        db.commit()

    produced = get_cycle_produced_by_product(
        db, optimization_cycle.id,
    )

    assert produced[test_products[0].id] == Decimal("20")

    consumed = get_cycle_consumed_by_resource(
        db, optimization_cycle.id,
    )

    assert consumed[test_resources[0].id] == Decimal("240")

    total = get_total_produced_by_product(db)

    assert total[test_products[0].id] == Decimal("20")


def test_has_application_for_run_detects_an_applied_run(
    db, cleanup_applications, optimization_cycle, test_products,
):
    from app.services.production_application import (
        has_application_for_run,
        save_production_application,
    )

    run = _make_run(db, optimization_cycle.id)

    assert has_application_for_run(db, run.id) is False

    save_production_application(
        db,
        optimization_cycle.id,
        run.id,
        {test_products[0].id: Decimal("10")},
        [],
    )
    db.commit()

    assert has_application_for_run(db, run.id) is True


def test_zero_and_negative_produced_quantities_are_skipped(
    db, cleanup_applications, optimization_cycle, test_products,
):
    """
    A plan can legitimately recommend 0 units of a product. Writing a
    zero row would add noise to the ledger without changing any
    derived figure, so it is skipped - matching apply_optimization's
    existing `if quantity <= 0: continue` rule for
    ProductionAllocation.
    """

    from app.services.production_application import (
        save_production_application,
    )

    run = _make_run(db, optimization_cycle.id)

    application = save_production_application(
        db,
        optimization_cycle.id,
        run.id,
        {
            test_products[0].id: Decimal("0"),
            test_products[1].id: Decimal("4"),
        },
        [],
    )

    db.commit()
    db.refresh(application)

    assert len(application.product_items) == 1
    assert application.product_items[0].product_id == (
        test_products[1].id
    )


def test_cycle_aggregates_are_scoped_to_their_cycle(
    db, cleanup_applications, optimization_cycle, test_products,
):
    """
    Cycle-scoped produced must reset for a new cycle while the
    all-cycles total keeps growing - that pairing is what preserves
    unsold stock across cycles.
    """

    from app.database.models import ProductionCycle
    from app.services.production_application import (
        get_cycle_produced_by_product,
        get_total_produced_by_product,
        save_production_application,
    )

    next_cycle = ProductionCycle(
        cycle_date=datetime(2026, 11, 6),
        start_date=datetime(2026, 11, 6),
        end_date=datetime(2026, 11, 13),
        status="OPEN",
    )

    db.add(next_cycle)
    db.commit()
    db.refresh(next_cycle)

    try:
        first_run = _make_run(db, optimization_cycle.id)

        save_production_application(
            db,
            optimization_cycle.id,
            first_run.id,
            {test_products[0].id: Decimal("10")},
            [],
        )
        db.commit()

        second_run = _make_run(db, next_cycle.id)

        save_production_application(
            db,
            next_cycle.id,
            second_run.id,
            {test_products[0].id: Decimal("6")},
            [],
        )
        db.commit()

        assert get_cycle_produced_by_product(
            db, next_cycle.id,
        )[test_products[0].id] == Decimal("6")

        assert get_cycle_produced_by_product(
            db, optimization_cycle.id,
        )[test_products[0].id] == Decimal("10")

        assert get_total_produced_by_product(
            db,
        )[test_products[0].id] == Decimal("16")

    finally:
        db.query(ProductionApplication).filter(
            ProductionApplication.production_cycle_id
            == next_cycle.id
        ).delete(synchronize_session=False)
        db.delete(next_cycle)
        db.commit()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_production_application.py -v
```

Expected: the 3 model tests pass; the 5 new ones fail with
`ModuleNotFoundError: No module named 'app.services.production_application'`.

- [ ] **Step 3: Write the service**

Create `backend/app/services/production_application.py`:

```python
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database.models import (
    ProductionApplication,
    ProductionApplicationItem,
    ProductionApplicationResourceItem,
)


def generate_application_number(db: Session) -> str:
    """
    "PA-0001", "PA-0002", ... - same sequential friendly-id convention
    as transaction.py::generate_transaction_number and
    resource_utilization_history.py::generate_utilization_number.
    """

    last_id = db.scalar(
        select(func.max(ProductionApplication.id))
    )

    return f"PA-{(last_id or 0) + 1:04d}"


def has_application_for_run(
    db: Session,
    optimization_run_id: int,
) -> bool:
    """
    Pre-flight duplicate check so the caller can return a clean,
    explanatory 400 instead of surfacing the
    uq_production_application_run IntegrityError. The constraint - not
    this - is the real guarantee; this only makes the common case
    readable.
    """

    return (
        db.scalar(
            select(func.count(ProductionApplication.id)).where(
                ProductionApplication.optimization_run_id
                == optimization_run_id
            )
        )
        or 0
    ) > 0


def save_production_application(
    db: Session,
    cycle_id: int,
    optimization_run_id: int,
    produced_by_product_id: dict[int, Decimal],
    consumed_resources: list[dict],
) -> ProductionApplication:
    """
    Appends one apply event plus its product and resource items.

    Deliberately does NOT commit - the caller
    (optimization.py::apply_optimization) commits this together with
    the ProductionAllocation rows and the resource utilization
    snapshot in one transaction, so production history, the current
    plan, and the utilization snapshot can never disagree about
    whether an apply happened. Same contract as
    resource_utilization_history.py::save_resource_utilization_history.

    Non-positive produced quantities are skipped rather than stored:
    they would add rows that change no derived figure, and
    apply_optimization already skips them for ProductionAllocation.
    """

    application = ProductionApplication(
        application_number=generate_application_number(db),
        production_cycle_id=cycle_id,
        optimization_run_id=optimization_run_id,
        applied_at=datetime.utcnow(),
    )

    db.add(application)
    db.flush()

    db.add_all(
        [
            ProductionApplicationItem(
                production_application_id=application.id,
                product_id=product_id,
                quantity_produced=quantity,
            )
            for product_id, quantity in (
                produced_by_product_id.items()
            )
            if quantity > 0
        ]
    )

    db.add_all(
        [
            ProductionApplicationResourceItem(
                production_application_id=application.id,
                resource_id=resource["resource_id"],
                resource_name=resource["resource_name"],
                unit=resource["unit"],
                consumed_quantity=resource["consumed_quantity"],
            )
            for resource in consumed_resources
            if resource["consumed_quantity"] > 0
        ]
    )

    db.flush()

    return application


def get_cycle_consumed_by_resource(
    db: Session,
    cycle_id: int,
) -> dict[int, Decimal]:
    """
    resource_id -> total raw material already consumed by every
    application in this cycle. Subtracted from
    CycleResource.available_quantity to get the capacity a NEW
    application may spend, which is what makes consumption
    incremental: an application can never re-use capacity an earlier
    one in the same cycle already used.

    Rows whose resource was later deleted (resource_id NULL, ON DELETE
    SET NULL) are excluded - there is no live CycleResource row to
    offset against, and inventing a key for them would corrupt the
    lookup.
    """

    rows = db.execute(
        select(
            ProductionApplicationResourceItem.resource_id,
            func.sum(
                ProductionApplicationResourceItem.consumed_quantity
            ),
        )
        .join(
            ProductionApplication,
            ProductionApplication.id
            == (
                ProductionApplicationResourceItem
                .production_application_id
            ),
        )
        .where(
            ProductionApplication.production_cycle_id == cycle_id,
            ProductionApplicationResourceItem.resource_id.isnot(
                None
            ),
        )
        .group_by(ProductionApplicationResourceItem.resource_id)
    ).all()

    return {
        resource_id: total
        for resource_id, total in rows
        if total is not None
    }


def get_cycle_produced_by_product(
    db: Session,
    cycle_id: int,
) -> dict[int, Decimal]:
    """
    product_id -> units produced by every application in THIS cycle.
    Resets naturally for a new cycle (no rows yet) while
    get_total_produced_by_product below keeps growing - that pairing
    is exactly how unsold stock survives a cycle boundary.
    """

    rows = db.execute(
        select(
            ProductionApplicationItem.product_id,
            func.sum(ProductionApplicationItem.quantity_produced),
        )
        .join(
            ProductionApplication,
            ProductionApplication.id
            == ProductionApplicationItem.production_application_id,
        )
        .where(
            ProductionApplication.production_cycle_id == cycle_id
        )
        .group_by(ProductionApplicationItem.product_id)
    ).all()

    return {
        product_id: total
        for product_id, total in rows
        if total is not None
    }


def get_total_produced_by_product(
    db: Session,
) -> dict[int, Decimal]:
    """
    product_id -> units produced across EVERY cycle, ever. The
    production half of available stock - deliberately never
    cycle-filtered, because stock that was produced and not sold is
    still stock after the cycle closes.
    """

    rows = db.execute(
        select(
            ProductionApplicationItem.product_id,
            func.sum(ProductionApplicationItem.quantity_produced),
        ).group_by(ProductionApplicationItem.product_id)
    ).all()

    return {
        product_id: total
        for product_id, total in rows
        if total is not None
    }


def get_applications(
    db: Session,
    cycle_id: int | None = None,
) -> list[ProductionApplication]:
    statement = (
        select(ProductionApplication)
        .options(
            selectinload(ProductionApplication.product_items),
            selectinload(ProductionApplication.resource_items),
        )
        .order_by(
            ProductionApplication.applied_at.desc(),
            ProductionApplication.id.desc(),
        )
    )

    if cycle_id is not None:
        statement = statement.where(
            ProductionApplication.production_cycle_id == cycle_id
        )

    return list(db.scalars(statement).all())
```

- [ ] **Step 4: Write the response schemas**

Create `backend/app/schemas/production_application.py`:

```python
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProductionApplicationItemResponse(BaseModel):
    product_id: int
    quantity_produced: Decimal

    model_config = ConfigDict(from_attributes=True)


class ProductionApplicationResourceItemResponse(BaseModel):
    # Nullable because the FK is ON DELETE SET NULL - resource_name
    # and unit are denormalised precisely so the row stays displayable
    # when this is None.
    resource_id: int | None
    resource_name: str
    unit: str
    consumed_quantity: Decimal

    model_config = ConfigDict(from_attributes=True)


class ProductionApplicationResponse(BaseModel):
    id: int
    application_number: str
    production_cycle_id: int
    optimization_run_id: int
    applied_at: datetime
    product_items: list[ProductionApplicationItemResponse]
    resource_items: list[
        ProductionApplicationResourceItemResponse
    ]

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_production_application.py -v
```

Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/production_application.py \
        backend/app/schemas/production_application.py \
        backend/tests/test_production_application.py
git commit -m "feat: production application ledger service

Append-only write path (no commit - the caller owns the transaction)
plus the cycle-scoped and all-cycles aggregate readers that stock
derivation and incremental capacity are built on.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 5: Incremental resource capacity in `find_resource_capacity_shortages`

**Requirements covered:** "Raw-material capacity: incremental consumption. Every new application must deduct resource consumption from previous applications in the same cycle."

**Design note:** the new parameter defaults to `None`, which reproduces today's behaviour exactly. Only the apply path passes it in Task 6. The two manual-allocation call sites in `services/allocation.py` are deliberately left on the old behaviour — see the Risks section for why, and the follow-up they imply.

**Files:**
- Modify: `backend/app/services/production_calculation.py:326-387` (`find_resource_capacity_shortages`)
- Test: `backend/tests/test_resource_usage_filtering.py` (append — this is where the existing capacity-guard unit tests live; confirm with `grep -n "find_resource_capacity_shortages" backend/tests/*.py` and append to whichever file already exercises it, otherwise create `backend/tests/test_incremental_capacity.py`)

**Interfaces:**
- Consumes: `get_cycle_consumed_by_resource` (Task 4).
- Produces: `find_resource_capacity_shortages(db, cycle_id, quantities_by_product_id, requirement_override=None, already_consumed_by_resource_id=None)`. Shortage dicts gain no new keys, but `available_quantity` now reports the *effective* (post-offset) figure so `format_capacity_shortage_message` tells the user what is actually left.

- [ ] **Step 1: Write the failing test**

Append (or create as noted above):

```python
from decimal import Decimal

from app.services.production_calculation import (
    find_resource_capacity_shortages,
)


def test_already_consumed_capacity_is_deducted(
    db, optimization_cycle, test_products, test_resources,
):
    """
    Incremental consumption: a quantity that fits inside the cycle's
    raw capacity must still be rejected once an earlier application in
    the same cycle has spent part of that capacity. Without the
    offset, the second application in a cycle would silently re-spend
    the first's materials.
    """

    chair = next(
        product for product in test_products
        if product.name == "Test Chair"
    )

    wood = next(
        resource for resource in test_resources
        if resource.name == "Test Wood"
    )

    # Baseline: this quantity fits when nothing has been consumed.
    assert (
        find_resource_capacity_shortages(
            db,
            optimization_cycle.id,
            {chair.id: Decimal("1")},
        )
        == []
    )

    # Reserve essentially all of the Wood capacity, then re-check the
    # same quantity: it must now be short.
    cycle_wood_capacity = next(
        cycle_resource.available_quantity
        for cycle_resource in optimization_cycle.cycle_resources
        if cycle_resource.resource_id == wood.id
    )

    shortages = find_resource_capacity_shortages(
        db,
        optimization_cycle.id,
        {chair.id: Decimal("1")},
        already_consumed_by_resource_id={
            wood.id: cycle_wood_capacity,
        },
    )

    assert [
        shortage["resource_id"] for shortage in shortages
    ] == [wood.id]

    # The reported availability must be the EFFECTIVE remainder, not
    # the raw cycle capacity - otherwise the error message tells the
    # user they have materials they have already spent.
    assert shortages[0]["available_quantity"] == Decimal("0")


def test_offset_never_reports_negative_availability(
    db, optimization_cycle, test_products, test_resources,
):
    """
    An over-consumed resource (capacity was reduced after an apply)
    must floor at zero rather than reporting a negative availability,
    which would make the shortage arithmetic in
    format_capacity_shortage_message read as nonsense.
    """

    chair = next(
        product for product in test_products
        if product.name == "Test Chair"
    )

    wood = next(
        resource for resource in test_resources
        if resource.name == "Test Wood"
    )

    shortages = find_resource_capacity_shortages(
        db,
        optimization_cycle.id,
        {chair.id: Decimal("1")},
        already_consumed_by_resource_id={
            wood.id: Decimal("999999"),
        },
    )

    wood_shortage = next(
        shortage for shortage in shortages
        if shortage["resource_id"] == wood.id
    )

    assert wood_shortage["available_quantity"] == Decimal("0")


def test_omitting_the_offset_preserves_existing_behaviour(
    db, optimization_cycle, test_products,
):
    """
    Every existing caller (manual allocation create/update,
    requirement edits) passes no offset and must behave exactly as
    before.
    """

    chair = next(
        product for product in test_products
        if product.name == "Test Chair"
    )

    assert find_resource_capacity_shortages(
        db,
        optimization_cycle.id,
        {chair.id: Decimal("1")},
    ) == find_resource_capacity_shortages(
        db,
        optimization_cycle.id,
        {chair.id: Decimal("1")},
        already_consumed_by_resource_id=None,
    )
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd backend && python -m pytest tests/test_incremental_capacity.py -v
```

Expected: `TypeError: find_resource_capacity_shortages() got an unexpected keyword argument 'already_consumed_by_resource_id'`.

- [ ] **Step 3: Add the offset parameter**

In `backend/app/services/production_calculation.py`, replace the signature and the availability
resolution inside `find_resource_capacity_shortages` (lines 326-384):

```python
def find_resource_capacity_shortages(
    db: Session,
    cycle_id: int,
    quantities_by_product_id: dict[int, Decimal],
    requirement_override: tuple[int, int, Decimal] | None = None,
    already_consumed_by_resource_id: dict[int, Decimal] | None = None,
) -> list[dict]:
    """
    Checks a PROPOSED set of product quantities against this cycle's
    CURRENT CycleResource capacity - an inactive resource is treated
    as zero available capacity here too (matching
    optimization.py::add_resource_constraints' convention), never its
    stale available_quantity, and never fabricated as unlimited when
    there's no CycleResource row for it at all this cycle. Returns one
    shortage dict per over-capacity resource - an empty list means the
    proposal fits entirely within current capacity.

    already_consumed_by_resource_id makes the check INCREMENTAL: the
    quantities passed in are validated against what is LEFT of each
    resource after earlier production applications in this same cycle
    have taken their share (see production_application.py::
    get_cycle_consumed_by_resource). Omitted/None reproduces the
    original non-incremental behaviour exactly, which is what every
    caller other than apply_optimization still wants - a manual
    allocation edit is a revision of the current plan, not an
    additional draw on materials.

    The offset is floored at zero: a resource whose capacity was
    reduced below what has already been consumed reports zero
    remaining, never a negative availability, so
    format_capacity_shortage_message's arithmetic stays readable.
    """

    consumption = calculate_resource_requirements_for_quantities(
        db,
        quantities_by_product_id,
        requirement_override,
    )

    cycle_resources_by_id = {
        cycle_resource.resource_id: cycle_resource
        for cycle_resource in db.scalars(
            select(CycleResource).where(
                CycleResource.production_cycle_id == cycle_id
            )
        ).all()
    }

    consumed_by_id = already_consumed_by_resource_id or {}

    shortages = []

    for item in consumption:
        cycle_resource = cycle_resources_by_id.get(item["resource_id"])

        if cycle_resource is None:
            available_quantity = Decimal("0")
        elif not item["resource_is_active"]:
            available_quantity = Decimal("0")
        else:
            available_quantity = max(
                Decimal("0"),
                cycle_resource.available_quantity
                - consumed_by_id.get(
                    item["resource_id"],
                    Decimal("0"),
                ),
            )

        required_quantity = item["required_quantity"]

        if required_quantity > available_quantity:
            shortages.append(
                {
                    "resource_id": item["resource_id"],
                    "resource_name": item["resource_name"],
                    "unit": item["unit"],
                    "required_quantity": required_quantity,
                    "available_quantity": available_quantity,
                    "shortage_quantity": (
                        required_quantity - available_quantity
                    ),
                }
            )

    return shortages
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd backend && python -m pytest tests/test_incremental_capacity.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Verify no existing caller regressed**

```bash
cd backend && python -m pytest tests/test_allocations.py tests/test_optimization.py \
  tests/test_resources.py tests/test_resource_usage_filtering.py -q
```

Expected: unchanged from the Task 0 baseline. All of these exercise the no-offset path.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/production_calculation.py \
        backend/tests/test_incremental_capacity.py
git commit -m "feat: optional already-consumed offset for capacity checks

Lets a caller validate a proposal against what is LEFT of each cycle
resource rather than its raw capacity. Omitted by every existing
caller, so behaviour is unchanged until apply_optimization opts in.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 6: Rewire `apply_optimization` — ledger write, duplicate rejection, incremental capacity, cycle lock

**Requirements covered:** "Only when the user clicks Apply to Production should the generated quantity be added"; "Every successfully applied allocation should add its production quantity. It must not overwrite previously applied production within the same cycle"; "Reject duplicate applications of the same optimization run"; "Raw-material capacity: incremental consumption"; "Prevent overselling under concurrent requests" (the apply half); "Keep ProductionAllocation unchanged as the current committed allocation."

**Design note:** `ProductionAllocation`'s delete-then-reinsert stays *exactly* as it is. What changes is that the capacity revalidation now runs against post-offset availability, a ledger row is appended in the same transaction, an already-applied run is rejected before anything is touched, and the whole function serialises on a `SELECT ... FOR UPDATE` of the cycle row.

**Files:**
- Modify: `backend/app/services/optimization.py:1-29` (imports), `1618-1790` (`apply_optimization`)
- Create: `backend/app/routers/production.py` addition — `GET /{cycle_id}/applications`
- Test: `backend/tests/test_production_apply_ledger.py` (new)

**Interfaces:**
- Consumes: `save_production_application`, `has_application_for_run`, `get_cycle_consumed_by_resource` (Task 4); `find_resource_capacity_shortages(..., already_consumed_by_resource_id=...)` (Task 5); `calculate_resource_requirements_for_quantities` (existing).
- Produces: `apply_optimization(db, cycle_id) -> dict` — same signature and same `build_optimization_result` return shape as today. No caller changes.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_production_apply_ledger.py`:

```python
from decimal import Decimal

from app.database.models import (
    ProductionAllocation,
    ProductionApplication,
)
from app.services.production_application import (
    get_cycle_produced_by_product,
)


def _optimize(client, cycle_id):
    response = client.post(
        f"/api/production-cycles/{cycle_id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )

    assert response.status_code == 200, response.text

    return response.json()


def _apply(client, cycle_id):
    return client.post(
        f"/api/production-cycles/{cycle_id}/optimize/apply",
    )


def test_generating_a_plan_writes_no_ledger_row(
    client, db, cleanup_applications, optimization_cycle,
):
    """
    Requirement 1: generating an allocation must not increase
    inventory. Already true today (generate only writes
    OptimizationRun/OptimizationResult) - pinned here so a future
    change cannot quietly break it.
    """

    _optimize(client, optimization_cycle.id)

    assert (
        db.query(ProductionApplication)
        .filter(
            ProductionApplication.production_cycle_id
            == optimization_cycle.id
        )
        .count()
        == 0
    )


def test_apply_appends_a_ledger_row_with_product_and_resource_items(
    client, db, cleanup_applications, optimization_cycle,
):
    _optimize(client, optimization_cycle.id)

    assert _apply(client, optimization_cycle.id).status_code == 200

    applications = (
        db.query(ProductionApplication)
        .filter(
            ProductionApplication.production_cycle_id
            == optimization_cycle.id
        )
        .all()
    )

    assert len(applications) == 1

    application = applications[0]

    assert application.product_items, (
        "apply must record what it produced"
    )
    assert application.resource_items, (
        "apply must record the capacity it consumed"
    )
    assert all(
        item.quantity_produced > 0
        for item in application.product_items
    )


def test_applying_the_same_run_twice_is_rejected(
    client, db, cleanup_applications, optimization_cycle,
):
    """
    Without this, a double-click adds the same units twice and
    available stock is permanently wrong.
    """

    _optimize(client, optimization_cycle.id)

    assert _apply(client, optimization_cycle.id).status_code == 200

    second = _apply(client, optimization_cycle.id)

    assert second.status_code == 400
    assert "already been applied" in second.json()["detail"].lower()

    assert (
        db.query(ProductionApplication)
        .filter(
            ProductionApplication.production_cycle_id
            == optimization_cycle.id
        )
        .count()
        == 1
    )


def test_a_new_run_can_be_applied_in_the_same_cycle_and_accumulates(
    client, db, cleanup_applications, optimization_cycle,
    test_resources,
):
    """
    The spec's Day-1/Day-5 scenario at the production level. The
    second apply needs fresh raw material (consumption is
    incremental), so capacity is topped up between applies - exactly
    what the shop does in reality.
    """

    from app.database.models import CycleResource

    _optimize(client, optimization_cycle.id)
    assert _apply(client, optimization_cycle.id).status_code == 200

    first_produced = get_cycle_produced_by_product(
        db, optimization_cycle.id,
    )

    assert first_produced

    # Top up every cycle resource so a second application has
    # materials to consume.
    for cycle_resource in db.query(CycleResource).filter(
        CycleResource.production_cycle_id == optimization_cycle.id
    ).all():
        cycle_resource.available_quantity = (
            cycle_resource.available_quantity * Decimal("3")
        )

    db.commit()

    _optimize(client, optimization_cycle.id)
    assert _apply(client, optimization_cycle.id).status_code == 200

    db.expire_all()

    second_produced = get_cycle_produced_by_product(
        db, optimization_cycle.id,
    )

    for product_id, first_quantity in first_produced.items():
        assert second_produced[product_id] > first_quantity, (
            "the second application must ADD to the cycle's produced "
            "total, not replace it"
        )

    assert (
        db.query(ProductionApplication)
        .filter(
            ProductionApplication.production_cycle_id
            == optimization_cycle.id
        )
        .count()
        == 2
    )


def test_a_second_apply_without_fresh_capacity_is_rejected(
    client, db, cleanup_applications, optimization_cycle,
):
    """
    Incremental consumption, enforced: with no capacity added, the
    second application has nothing left to consume and must be
    rejected with a capacity message rather than silently re-spending
    the first application's materials.
    """

    _optimize(client, optimization_cycle.id)
    assert _apply(client, optimization_cycle.id).status_code == 200

    _optimize(client, optimization_cycle.id)
    second = _apply(client, optimization_cycle.id)

    assert second.status_code == 400
    assert "capacity" in second.json()["detail"].lower()

    assert (
        db.query(ProductionApplication)
        .filter(
            ProductionApplication.production_cycle_id
            == optimization_cycle.id
        )
        .count()
        == 1
    )


def test_production_allocation_still_holds_only_the_latest_plan(
    client, db, cleanup_applications, optimization_cycle,
):
    """
    ProductionAllocation's contract is unchanged: one row per product,
    replaced wholesale on each apply. The LEDGER accumulates; the
    allocation does not. Pinned so a future change cannot blur the
    two.
    """

    from app.database.models import CycleResource

    _optimize(client, optimization_cycle.id)
    _apply(client, optimization_cycle.id)

    for cycle_resource in db.query(CycleResource).filter(
        CycleResource.production_cycle_id == optimization_cycle.id
    ).all():
        cycle_resource.available_quantity = (
            cycle_resource.available_quantity * Decimal("3")
        )

    db.commit()

    _optimize(client, optimization_cycle.id)
    _apply(client, optimization_cycle.id)

    db.expire_all()

    allocations = (
        db.query(ProductionAllocation)
        .filter(
            ProductionAllocation.production_cycle_id
            == optimization_cycle.id
        )
        .all()
    )

    product_ids = [row.product_id for row in allocations]

    assert len(product_ids) == len(set(product_ids)), (
        "ProductionAllocation must still be one row per product"
    )


def test_a_rejected_apply_leaves_no_ledger_row(
    client, db, cleanup_applications, optimization_cycle,
    test_resources,
):
    """
    Atomicity: a capacity rejection must not leave a half-written
    application behind, or stock would count units that were never
    produced.
    """

    from app.database.models import CycleResource

    _optimize(client, optimization_cycle.id)

    for cycle_resource in db.query(CycleResource).filter(
        CycleResource.production_cycle_id == optimization_cycle.id
    ).all():
        cycle_resource.available_quantity = Decimal("0")

    db.commit()

    response = _apply(client, optimization_cycle.id)

    assert response.status_code == 400

    assert (
        db.query(ProductionApplication)
        .filter(
            ProductionApplication.production_cycle_id
            == optimization_cycle.id
        )
        .count()
        == 0
    )


def test_applications_endpoint_lists_the_ledger(
    client, db, cleanup_applications, optimization_cycle,
):
    _optimize(client, optimization_cycle.id)
    _apply(client, optimization_cycle.id)

    response = client.get(
        f"/api/production-cycles/{optimization_cycle.id}/applications",
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["application_number"].startswith("PA-")
    assert payload[0]["product_items"]
    assert payload[0]["resource_items"]
```

**[SUPERSEDED BY AMENDMENT C — DO NOT PERFORM THIS STEP.]** G1.6 already moved
`cleanup_applications` into `backend/tests/conftest.py`, where it delegates to the shared
`purge_ledger()` helper (which carries the mandatory `db.rollback()`, the five-table FK order,
and six call sites including the row-owning fixtures). Use the existing fixture as-is.
Re-adding, moving, or overwriting it with the body below would drop the rollback fix and the
opening-inventory tables and re-introduce the 30-error teardown regression recorded under
Ruling 21.

The original — now historical — instruction and body were:

> Also copy the `cleanup_applications` fixture from `backend/tests/test_production_application.py`
> into `backend/tests/conftest.py` so both files share it, and delete the local copy from
> `test_production_application.py`. Place it after the existing `cleanup_test_data` fixture:

```python
@pytest.fixture
def cleanup_applications(db):
    """
    Shared by test_production_application.py and
    test_production_apply_ledger.py - the ledger is append-only in
    production, so tests must clear it explicitly rather than relying
    on any delete path existing in the application.
    """

    from app.database.models import (
        ProductionApplication,
        ProductionApplicationItem,
        ProductionApplicationResourceItem,
    )

    def _purge():
        db.query(ProductionApplicationResourceItem).delete(
            synchronize_session=False
        )
        db.query(ProductionApplicationItem).delete(
            synchronize_session=False
        )
        db.query(ProductionApplication).delete(
            synchronize_session=False
        )
        db.commit()

    _purge()

    yield

    _purge()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_production_apply_ledger.py -v
```

Expected: `test_generating_a_plan_writes_no_ledger_row` passes; the rest fail (no ledger rows
written, second apply succeeds instead of 400, `/applications` returns 404).

- [ ] **Step 3: Extend the imports in `backend/app/services/optimization.py`**

Add to the existing import block (lines 8-29):

```python
from app.database.models import (
    CycleResource,
    Product,
    ProductResourceRequirement,
    ProductionAllocation,
    ProductionCycle,
    Resource,
)
from app.services.optimization_history import (
    get_latest_optimization_history_run,
)
from app.services.production_application import (
    get_cycle_consumed_by_resource,
    has_application_for_run,
    save_production_application,
)
from app.services.production_calculation import (
    BOTTLENECK_REMAINING_THRESHOLD,
    calculate_resource_requirements_for_quantities,
    find_resource_capacity_shortages,
    format_capacity_shortage_message,
)
```

- [ ] **Step 4: Rewire `apply_optimization`**

In `backend/app/services/optimization.py`, replace the body of `apply_optimization` from the
`optimization_run = (` assignment (line ~1632) down to the `db.commit()` in the `try` block
(line ~1783). Keep `get_optimization_data`, the `cycle_resources` emptiness check, and the final
`return build_optimization_result(...)` exactly as they are.

```python
    # Serialises concurrent applies for this cycle. Two parallel
    # clicks would otherwise both read the same already-consumed
    # offset, both pass the capacity check, and both append a ledger
    # row - double-counting units into available stock. The
    # uq_production_application_run constraint catches the identical-
    # run case regardless, but two DIFFERENT runs applied
    # simultaneously would slip past it, so the lock is what makes
    # incremental capacity actually incremental. Held until this
    # function's commit/rollback.
    locked_cycle = db.execute(
        select(ProductionCycle)
        .where(ProductionCycle.id == cycle_id)
        .with_for_update()
    ).scalar_one_or_none()

    if locked_cycle is None:
        raise ValueError("Production cycle not found")

    optimization_run = (
        get_latest_optimization_history_run(
            db,
            cycle_id,
        )
    )

    if optimization_run is None:
        raise ValueError(
            "No optimization result found for production cycle."
        )

    if optimization_run.status != "OPTIMAL":
        raise ValueError(
            "Only an optimal optimization result can be applied."
        )

    # Both guards run BEFORE the ProductionAllocation delete further
    # down: a summary-only imported record (or any run that somehow has
    # no per-product rows) would otherwise clear every current
    # allocation, insert none, and commit a zero-utilization snapshot
    # as if it were a real applied plan.
    if optimization_run.is_summary_only:
        raise ValueError(
            "This optimization record is summary-only and cannot be "
            "applied. Generate a new production plan instead."
        )

    if not optimization_run.results:
        raise ValueError(
            "This optimization record has no product-level results and "
            "cannot be applied. Generate a new production plan instead."
        )

    # Duplicate-application guard. Checked here, before anything is
    # written, so the caller gets an explanatory 400 instead of the
    # uq_production_application_run IntegrityError - and so a
    # double-clicked Apply cannot add the same units to available
    # stock twice. Deliberately phrased as "generate a new plan":
    # re-applying is never the right remedy, producing more is.
    if has_application_for_run(db, optimization_run.id):
        raise ValueError(
            "This production plan has already been applied "
            "and cannot be applied again. Generate a new production "
            "plan to produce more."
        )

    allocations = []

    for result in optimization_run.results:
        product = next(
            (
                product
                for product in data["products"]
                if product.id == result.product_id
            ),
            None,
        )

        if product is None:
            continue

        quantity = int(result.recommended_quantity)
        minimum_demand = product.minimum_demand or Decimal("0")

        allocations.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "quantity": quantity,
                "unit_profit": result.unit_profit,
                "total_profit": result.total_profit,
                "minimum_demand": minimum_demand,
                "shortfall": max(
                    Decimal("0"),
                    minimum_demand - Decimal(str(quantity)),
                ),
            }
        )

    if not any(
        allocation["quantity"] > 0
        for allocation in allocations
    ):
        raise ValueError(
            "This optimization record has no applicable product-level "
            "results. Generate a new production plan instead."
        )

    # Revalidate the ENTIRE proposed allocation against current
    # resource state before touching the database at all - the saved
    # OptimizationResult rows reflect whatever CycleResource/
    # ProductResourceRequirement looked like the last time /optimize
    # ran, which may no longer be true by the time Apply is clicked.
    #
    # INCREMENTAL since the production ledger exists: capacity already
    # consumed by earlier applications in THIS cycle is deducted
    # first, so a second application cannot re-spend the first's
    # materials. A cycle with no prior application gets an empty
    # offset and behaves exactly as before.
    proposed_quantities = {
        allocation["product_id"]: Decimal(str(allocation["quantity"]))
        for allocation in allocations
    }

    already_consumed = get_cycle_consumed_by_resource(db, cycle_id)

    shortages = find_resource_capacity_shortages(
        db,
        cycle_id,
        proposed_quantities,
        already_consumed_by_resource_id=already_consumed,
    )

    if shortages:
        raise ValueError(
            format_capacity_shortage_message(
                shortages,
                "Cannot apply this production plan - the cycle does "
                "not have enough remaining resource capacity "
                "(previous applications in this cycle have already "
                "consumed part of it). Increase the resource "
                "quantities or regenerate the Production Plan",
            )
        )

    # What this application will consume, recorded on the ledger so the
    # NEXT application in this cycle is offset by it. Computed from the
    # same helper find_resource_capacity_shortages just validated
    # against, so the recorded consumption and the validated
    # consumption can never be two different numbers.
    consumption = calculate_resource_requirements_for_quantities(
        db,
        proposed_quantities,
    )

    consumed_resources = [
        {
            "resource_id": item["resource_id"],
            "resource_name": item["resource_name"],
            "unit": item["unit"],
            "consumed_quantity": item["required_quantity"],
        }
        for item in consumption
    ]

    db.query(ProductionAllocation).filter(
        ProductionAllocation.production_cycle_id == cycle_id
    ).delete(
        synchronize_session=False
    )

    applied_at = datetime.utcnow()

    for allocation in allocations:
        quantity = allocation["quantity"]

        if quantity <= 0:
            continue

        db.add(
            ProductionAllocation(
                production_cycle_id=cycle_id,
                product_id=allocation["product_id"],
                quantity=quantity,
                applied_at=applied_at,
            )
        )

    try:
        # Flushed (not committed) so calculate_resource_utilization()
        # below - which reads ProductionAllocation back via a SELECT
        # - sees the rows just added above in this same session.
        # autoflush is disabled project-wide (see
        # app/database/connection.py), so without this the query
        # would still see the pre-apply allocations.
        db.flush()

        # Append-only production history. Written in the SAME
        # transaction as the ProductionAllocation rows and the
        # utilization snapshot below, so the current plan, the
        # production history, and the utilization snapshot can never
        # disagree about whether this apply happened.
        save_production_application(
            db,
            cycle_id,
            optimization_run.id,
            {
                allocation["product_id"]: Decimal(
                    str(allocation["quantity"])
                )
                for allocation in allocations
            },
            consumed_resources,
        )

        # Resource Utilization History is a snapshot of applied
        # production, never of the optimizer's preview - this is the
        # ONLY place it's created. Passed the cycle's CUMULATIVE
        # ledger consumption rather than letting it re-derive
        # consumption from ProductionAllocation: the allocation holds
        # only the latest plan, so without this the snapshot taken
        # after a second application would report the cycle as having
        # consumed only that application's share and show capacity the
        # cycle has already spent.
        cumulative_consumed = get_cycle_consumed_by_resource(
            db,
            cycle_id,
        )

        utilization = calculate_resource_utilization(
            db,
            cycle_id,
            consumption_override=cumulative_consumed,
        )

        save_resource_utilization_history(
            db,
            cycle_id,
            utilization,
        )

        db.commit()
    except Exception:
        db.rollback()
        raise
```

**Implementer note:** `get_cycle_consumed_by_resource` is called twice on purpose — once *before*
the write (the offset this application is validated against) and once *after*
`save_production_application`'s flush (the cumulative figure the snapshot should show, which now
includes this application). Do not collapse them into one call.

- [ ] **Step 5: Add the applications listing endpoint**

In `backend/app/routers/production.py`, add the import:

```python
from app.schemas.production_application import (
    ProductionApplicationResponse,
)
from app.services.production_application import get_applications
```

and register the route **before** the catch-all `GET /{cycle_id}` at the bottom of the file
(same registration-order reasoning as `/latest`):

```python
@router.get(
    "/{cycle_id}/applications",
    response_model=list[ProductionApplicationResponse],
    summary="List production applications for a cycle",
)
def list_production_applications(
    cycle_id: int,
    db: Session = Depends(get_db),
):
    return get_applications(db, cycle_id)
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_production_apply_ledger.py -v
```

Expected: 8 passed. Task 7 must be completed for the `consumption_override` keyword to exist — if
`calculate_resource_utilization` raises `TypeError: unexpected keyword argument`, do Task 7 first
and re-run. (They are split because each is independently reviewable; if executing strictly in
order, implement Task 7 Step 3 before this step and tick it off there.)

- [ ] **Step 7: Verify the existing optimization/apply suite**

```bash
cd backend && python -m pytest tests/test_optimization.py \
  tests/test_optimization_history_lifecycle.py tests/test_resource_utilization.py \
  tests/test_resource_utilization_history.py -q
```

Expected: `test_generate_then_apply_restores_the_production_workflow` and
`test_summary_only_records_are_never_selected_or_applied`
(`tests/test_optimization_history_lifecycle.py:547,626`) still pass. If any test applies the same
run twice as a setup convenience, it will now get a 400 — update that test to generate a fresh plan
between applies, and note it in the commit message.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/optimization.py backend/app/routers/production.py \
        backend/tests/test_production_apply_ledger.py backend/tests/conftest.py \
        backend/tests/test_production_application.py
git commit -m "feat: apply writes an append-only ledger row with incremental capacity

Apply now rejects an already-applied run, validates against capacity
remaining after earlier applications in the cycle, records what it
consumed, and serialises on the cycle row. ProductionAllocation keeps
its replace-the-latest-plan contract unchanged.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 7: Cumulative resource utilization snapshot

**Requirements covered:** supports "Raw-material capacity: incremental consumption" — the utilization report must not show capacity the cycle has already spent.

**Design note:** the parameter defaults to `None`, which keeps the live Resource Utilization report and every existing test on today's allocation-derived behaviour. The router opts in only when the cycle actually has ledger rows, so legacy cycles with no applications are byte-for-byte unchanged.

**Files:**
- Modify: `backend/app/services/resource_utilization.py:63-94` (`calculate_resource_utilization`)
- Modify: `backend/app/routers/resource_utilization.py` (opt in for cycles that have applications)
- Test: `backend/tests/test_resource_utilization.py` (append)

**Interfaces:**
- Consumes: `get_cycle_consumed_by_resource` (Task 4).
- Produces: `calculate_resource_utilization(db, cycle_id, consumption_override=None) -> dict` — same return shape.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_resource_utilization.py`:

```python
def test_consumption_override_replaces_allocation_derived_consumption(
    db, optimization_cycle, test_resources,
):
    """
    After a second application in a cycle, ProductionAllocation holds
    only the latest plan - so allocation-derived consumption
    understates what the cycle has actually spent. The override lets
    the caller supply the cumulative ledger figure instead.
    """

    from decimal import Decimal

    from app.services.resource_utilization import (
        calculate_resource_utilization,
    )

    wood = next(
        resource for resource in test_resources
        if resource.name == "Test Wood"
    )

    result = calculate_resource_utilization(
        db,
        optimization_cycle.id,
        consumption_override={wood.id: Decimal("7")},
    )

    wood_row = next(
        row for row in result["resources"]
        if row["resource_id"] == wood.id
    )

    assert wood_row["consumed_quantity"] == Decimal("7")
    assert wood_row["remaining_quantity"] == (
        wood_row["available_quantity"] - Decimal("7")
    )


def test_omitting_the_override_preserves_allocation_derived_behaviour(
    db, optimization_cycle,
):
    from app.services.resource_utilization import (
        calculate_resource_utilization,
    )

    assert calculate_resource_utilization(
        db, optimization_cycle.id,
    ) == calculate_resource_utilization(
        db, optimization_cycle.id, consumption_override=None,
    )
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd backend && python -m pytest tests/test_resource_utilization.py -k override -v
```

Expected: `TypeError: calculate_resource_utilization() got an unexpected keyword argument 'consumption_override'`.

- [ ] **Step 3: Add the parameter**

In `backend/app/services/resource_utilization.py`, change the signature and the
`consumption_by_resource` assignment (lines 63-94):

```python
def calculate_resource_utilization(
    db: Session,
    cycle_id: int,
    consumption_override: dict[int, Decimal] | None = None,
) -> dict:
    """
    Aggregate resource utilization for a production cycle from
    existing cycle resource capacity and existing allocation-based
    consumption calculations.

    consumption_override replaces the allocation-derived consumption
    with an explicit resource_id -> consumed mapping. Needed because
    ProductionAllocation holds only the CURRENT plan for a cycle: once
    a cycle has had more than one production application, consumption
    derived from the allocation understates what the cycle has
    actually spent, and the report would show capacity that is already
    gone. Callers that have the cumulative ledger figure (see
    production_application.py::get_cycle_consumed_by_resource) pass it
    here. None keeps the original allocation-derived behaviour, which
    is still correct for a cycle with at most one application.
    """

    cycle_resources = get_cycle_resources(db, cycle_id)

    if not cycle_resources:
        return {
            "cycle_id": cycle_id,
            "overall_utilization_rate": Decimal("0.00"),
            "total_raw_materials_consumed": Decimal("0"),
            "total_labor_hours_used": Decimal("0"),
            "total_labor_hours_capacity": Decimal("0"),
            "total_machine_hours_used": Decimal("0"),
            "total_machine_hours_capacity": Decimal("0"),
            "material_resource_count": 0,
            "most_constrained_resource": None,
            "at_risk_resources": [],
            "resources": [],
            "bottlenecks": [],
        }

    if consumption_override is not None:
        consumption_by_resource = consumption_override
    else:
        consumption_by_resource = {
            item["resource_id"]: item["required_quantity"]
            for item in calculate_resource_consumption(db, cycle_id)
        }
```

Leave the rest of the function exactly as it is.

- [ ] **Step 4: Opt in from the live utilization router**

In `backend/app/routers/resource_utilization.py`, add:

```python
from app.services.production_application import (
    get_cycle_consumed_by_resource,
)
```

and in whichever handler calls `calculate_resource_utilization(db, cycle_id)` for the *current*
cycle, replace the call with:

```python
    # A cycle that has had production applications must report the
    # cumulative consumption those applications recorded, not what the
    # latest ProductionAllocation alone implies - otherwise the report
    # shows capacity the cycle has already spent. A cycle with no
    # applications (every pre-ledger cycle) gets an empty dict, which
    # falls back to the original allocation-derived path.
    consumed = get_cycle_consumed_by_resource(db, cycle_id)

    utilization = calculate_resource_utilization(
        db,
        cycle_id,
        consumption_override=consumed or None,
    )
```

Locate the exact handler with `grep -n "calculate_resource_utilization" backend/app/routers/resource_utilization.py`
and apply the change at each site that serves the current cycle. Do **not** change any path that
reads `ResourceUtilizationHistoryItem` — historical snapshots are never recalculated.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_resource_utilization.py \
  tests/test_resource_utilization_history.py -v
```

Expected: all pass, including the two new ones.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/resource_utilization.py \
        backend/app/routers/resource_utilization.py \
        backend/tests/test_resource_utilization.py
git commit -m "feat: utilization can report cumulative ledger consumption

ProductionAllocation holds only the latest plan, so a cycle with two
applications needs the ledger's cumulative figure or the report shows
capacity already spent. Opt-in; legacy cycles are unchanged.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 8: `sales_transactions.production_cycle_id` + strict cycle resolution

**Requirements covered:** "Add nullable production_cycle_id to sales_transactions"; "Reject transactions whose dates do not match a production cycle rather than silently assigning them to the latest cycle"; "Preserve unsold stock across production cycles while resetting cycle-specific production and sales totals" (the sold half).

**Cycle window rule (decide once, here):** a transaction belongs to the cycle where
`date(start_date) <= date(transaction_date) < date(end_date)` — **half-open on the end**. This is
the only rule that makes `seed.py:306`'s `end_date = start_date + timedelta(days=7)` mean exactly
seven days *and* keeps back-to-back cycles non-overlapping. Comparison is on the calendar date
component only, because `transaction_date` arrives from the UI as `YYYY-MM-DDT00:00:00` while cycle
dates may carry a time, and a raw timestamp comparison would make membership depend on the
browser's clock. If legacy data somehow produces two matching cycles, the request is rejected as
ambiguous rather than resolved by a tiebreak — a silent pick is exactly what the requirement
forbids.

**Files:**
- Modify: `backend/app/database/models.py` (`SalesTransaction`: add `production_cycle_id` + relationship)
- Create: `backend/alembic/versions/<rev>_add_production_cycle_to_sales_transactions.py`
- Modify: `backend/app/services/transaction.py:1-13` (imports), add `resolve_production_cycle_for_date`
- Modify: `backend/app/schemas/transaction.py` (`SalesTransactionResponse`: add `production_cycle_id`)
- Test: `backend/tests/test_transaction_cycle_resolution.py` (new)

**Interfaces:**
- Consumes: `ProductionCycle`.
- Produces: `SalesTransaction.production_cycle_id: int | None`; `resolve_production_cycle_for_date(db, transaction_date) -> ProductionCycle` raising `ValueError` when no or multiple cycles match; `SalesTransactionResponse.production_cycle_id: int | None`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_transaction_cycle_resolution.py`:

```python
from datetime import datetime

import pytest

from app.database.models import ProductionCycle, SalesTransaction


@pytest.fixture
def two_cycles(db):
    """
    Two back-to-back 7-day cycles. Under the half-open rule they must
    not overlap: Nov 6 belongs to the second cycle only.
    """

    first = ProductionCycle(
        cycle_date=datetime(2026, 10, 30),
        start_date=datetime(2026, 10, 30),
        end_date=datetime(2026, 11, 6),
        status="OPEN",
    )

    second = ProductionCycle(
        cycle_date=datetime(2026, 11, 6),
        start_date=datetime(2026, 11, 6),
        end_date=datetime(2026, 11, 13),
        status="OPEN",
    )

    db.add_all([first, second])
    db.commit()
    db.refresh(first)
    db.refresh(second)

    yield first, second

    db.query(SalesTransaction).filter(
        SalesTransaction.production_cycle_id.in_(
            [first.id, second.id]
        )
    ).delete(synchronize_session=False)
    db.delete(first)
    db.delete(second)
    db.commit()


def test_resolves_a_date_inside_a_cycle(db, two_cycles):
    from app.services.transaction import (
        resolve_production_cycle_for_date,
    )

    first, _ = two_cycles

    resolved = resolve_production_cycle_for_date(
        db, datetime(2026, 11, 2),
    )

    assert resolved.id == first.id


def test_start_date_is_inclusive(db, two_cycles):
    from app.services.transaction import (
        resolve_production_cycle_for_date,
    )

    first, _ = two_cycles

    assert resolve_production_cycle_for_date(
        db, datetime(2026, 10, 30),
    ).id == first.id


def test_end_date_belongs_to_the_next_cycle(db, two_cycles):
    """
    Half-open: Nov 6 is the first cycle's end_date and the second
    cycle's start_date, and must resolve to the second - otherwise
    back-to-back cycles overlap and every boundary date is ambiguous.
    """

    from app.services.transaction import (
        resolve_production_cycle_for_date,
    )

    _, second = two_cycles

    assert resolve_production_cycle_for_date(
        db, datetime(2026, 11, 6),
    ).id == second.id


def test_a_date_in_no_cycle_is_rejected(db, two_cycles):
    """
    The requirement is explicit: reject, never fall back to the latest
    cycle. A sale silently attributed to the wrong cycle corrupts that
    cycle's sold total and the stock figure derived alongside it.
    """

    from app.services.transaction import (
        resolve_production_cycle_for_date,
    )

    with pytest.raises(ValueError) as error:
        resolve_production_cycle_for_date(
            db, datetime(2027, 6, 1),
        )

    message = str(error.value).lower()

    assert "production cycle" in message
    assert "2027-06-01" in str(error.value)


def test_overlapping_cycles_are_rejected_as_ambiguous(db):
    """
    Legacy/hand-created cycles can overlap. Picking one would be the
    silent assignment the requirement forbids, so the request is
    rejected and the user is told which cycles collide.
    """

    from app.services.transaction import (
        resolve_production_cycle_for_date,
    )

    overlapping = [
        ProductionCycle(
            cycle_date=datetime(2026, 12, 1),
            start_date=datetime(2026, 12, 1),
            end_date=datetime(2026, 12, 10),
            status="OPEN",
        ),
        ProductionCycle(
            cycle_date=datetime(2026, 12, 5),
            start_date=datetime(2026, 12, 5),
            end_date=datetime(2026, 12, 15),
            status="OPEN",
        ),
    ]

    db.add_all(overlapping)
    db.commit()

    try:
        with pytest.raises(ValueError) as error:
            resolve_production_cycle_for_date(
                db, datetime(2026, 12, 7),
            )

        assert "more than one" in str(error.value).lower()

    finally:
        for cycle in overlapping:
            db.delete(cycle)

        db.commit()


def test_created_transaction_carries_its_cycle(
    client, db, two_cycles, test_products,
):
    first, _ = two_cycles

    response = client.post(
        "/api/transactions",
        json={
            "product_id": test_products[0].id,
            "transaction_date": "2026-11-02T00:00:00",
            "quantity_produced": 5,
            "quantity": 2,
            "unit_price": 100,
            "production_cost": 0,
        },
    )

    assert response.status_code == 201
    assert response.json()["production_cycle_id"] == first.id


def test_create_rejects_a_date_outside_every_cycle(
    client, two_cycles, test_products,
):
    response = client.post(
        "/api/transactions",
        json={
            "product_id": test_products[0].id,
            "transaction_date": "2027-06-01T00:00:00",
            "quantity_produced": 5,
            "quantity": 2,
            "unit_price": 100,
            "production_cost": 0,
        },
    )

    assert response.status_code == 400
    assert "production cycle" in response.json()["detail"].lower()


def test_existing_rows_keep_a_null_cycle(db):
    """
    The column is nullable precisely so no backfill is needed: a
    pre-migration row has no reliable cycle, and inventing one would
    put fabricated numbers into a cycle's sold total. Such rows still
    count toward ALL-TIME sold (and therefore stock), just not toward
    any cycle's figures.
    """

    row = SalesTransaction(
        transaction_number="TRX-CYCLENULL",
        product_id=db.query(SalesTransaction.product_id).first()[0]
        if db.query(SalesTransaction).count()
        else 1,
        transaction_date=datetime(2020, 1, 1),
        quantity_produced=1,
        quantity=1,
        unit_price=1,
        total_sales=1,
        production_cost=0,
        unit_profit=1,
        total_profit=1,
    )

    db.add(row)
    db.commit()

    try:
        db.refresh(row)

        assert row.production_cycle_id is None

    finally:
        db.delete(row)
        db.commit()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_transaction_cycle_resolution.py -v
```

Expected: `ImportError: cannot import name 'resolve_production_cycle_for_date'`.

- [ ] **Step 3: Add the column to the model**

In `backend/app/database/models.py`, inside `SalesTransaction`, directly after `product_id`:

```python
    # Which 7-day production cycle this sale belongs to, resolved from
    # transaction_date at creation time (see services/transaction.py::
    # resolve_production_cycle_for_date). Drives the CYCLE-SCOPED sold
    # total; all-time sold - and therefore available stock - never
    # filters on it, so a sale always reduces stock regardless of
    # which cycle it landed in.
    #
    # Nullable, and deliberately never backfilled: rows created before
    # this column existed have no reliable cycle, and inventing one
    # would inject fabricated numbers into a real cycle's reported
    # sales. ON DELETE SET NULL for the same reason - deleting a cycle
    # must not delete sales history.
    production_cycle_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "production_cycles.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
```

and after the existing `product` relationship:

```python
    production_cycle: Mapped["ProductionCycle | None"] = relationship()
```

- [ ] **Step 4: Write the migration**

```bash
cd backend && python -m alembic revision -m "add production cycle to sales transactions"
```

`down_revision` = Task 3's revision id. Body:

```python
def upgrade() -> None:
    # Nullable with NO backfill on purpose: a pre-existing row has no
    # reliable production cycle, and guessing one would put invented
    # numbers into a real cycle's reported sales. Such rows still count
    # toward all-time sold (and therefore available stock) - only the
    # per-cycle breakdown excludes them.
    op.add_column(
        "sales_transactions",
        sa.Column("production_cycle_id", sa.Integer(), nullable=True),
    )

    op.create_index(
        op.f("ix_sales_transactions_production_cycle_id"),
        "sales_transactions",
        ["production_cycle_id"],
    )

    op.create_foreign_key(
        "fk_sales_transactions_production_cycle_id",
        "sales_transactions",
        "production_cycles",
        ["production_cycle_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_sales_transactions_production_cycle_id",
        "sales_transactions",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_sales_transactions_production_cycle_id"),
        table_name="sales_transactions",
    )
    op.drop_column("sales_transactions", "production_cycle_id")
```

- [ ] **Step 5: Write the resolver**

In `backend/app/services/transaction.py`, extend the imports:

```python
from app.database.models import Product, ProductionCycle, SalesTransaction
```

and add after `validate_transaction_date_range`:

```python
def resolve_production_cycle_for_date(
    db: Session,
    transaction_date: datetime,
) -> ProductionCycle:
    """
    The production cycle a sale belongs to, by date.

    Membership is HALF-OPEN on the end bound:
    date(start_date) <= date(transaction_date) < date(end_date). That
    is the only rule under which seed.py's
    `end_date = start_date + timedelta(days=7)` describes exactly
    seven days AND back-to-back cycles never overlap - an inclusive
    end bound would make every boundary date belong to two cycles.

    Compared on the calendar DATE component only: transaction_date
    arrives from the UI as YYYY-MM-DDT00:00:00 while cycle bounds may
    carry a time, so a raw timestamp comparison would make cycle
    membership depend on the submitting browser's clock.

    Raises rather than falling back to the latest cycle. A sale
    attributed to the wrong cycle silently corrupts that cycle's
    reported sales and the stock figures derived alongside them, so an
    unmatched date must be the user's problem to fix, not something
    the system papers over. Two matching cycles (possible only with
    hand-created overlapping cycles) are likewise rejected rather than
    resolved by a tiebreak - picking one would be exactly the silent
    assignment this function exists to prevent.
    """

    target_day = transaction_date.date()

    matches = list(
        db.scalars(
            select(ProductionCycle)
            .where(
                cast(ProductionCycle.start_date, Date)
                <= target_day,
                cast(ProductionCycle.end_date, Date) > target_day,
            )
            .order_by(ProductionCycle.id)
        ).all()
    )

    if not matches:
        raise ValueError(
            f"{target_day.isoformat()} does not fall within any "
            "production cycle. Create or adjust a production cycle "
            "that covers this date, then record the transaction."
        )

    if len(matches) > 1:
        names = ", ".join(
            f"#{cycle.id} "
            f"({cycle.start_date.date().isoformat()} to "
            f"{cycle.end_date.date().isoformat()})"
            for cycle in matches
        )

        raise ValueError(
            f"{target_day.isoformat()} falls within more than one "
            f"production cycle ({names}). Correct the overlapping "
            "cycle dates before recording this transaction."
        )

    return matches[0]
```

- [ ] **Step 6: Set the column on create**

In `backend/app/services/transaction.py::create_transaction`, after the `is_active` check and before
`calculate_transaction_values`:

```python
    production_cycle = resolve_production_cycle_for_date(
        db,
        transaction_data.transaction_date,
    )
```

and add to the `SalesTransaction(...)` constructor:

```python
        production_cycle_id=production_cycle.id,
```

- [ ] **Step 7: Expose it on the response**

In `backend/app/schemas/transaction.py::SalesTransactionResponse`, after `product_id`:

```python
    # Null only for rows created before this column existed - see
    # app/database/models.py::SalesTransaction.production_cycle_id for
    # why those are never backfilled.
    production_cycle_id: int | None
```

- [ ] **Step 8: Apply the migration and run the tests**

```bash
cd backend && TEST_DATABASE_URL="$(grep -h '^TEST_DATABASE_URL=' .env.test | cut -d= -f2-)" \
  DATABASE_URL="$TEST_DATABASE_URL" python -m alembic upgrade head \
  && python -m pytest tests/test_transaction_cycle_resolution.py -v
```

Expected: 8 passed.

- [ ] **Step 9: Fix the now-failing existing transaction tests**

Every test in `backend/tests/test_transactions.py` and
`backend/tests/test_transaction_date_filter.py` that POSTs a transaction will now get a 400 unless
its `transaction_date` falls inside a production cycle.

```bash
cd backend && python -m pytest tests/test_transactions.py tests/test_transaction_date_filter.py -v
```

For each failure, add the `two_cycles`-style fixture (or reuse `optimization_cycle` and pick a date
inside its window) rather than loosening the resolver. Move the `two_cycles` fixture from
`test_transaction_cycle_resolution.py` into `backend/tests/conftest.py` so all three files share it,
and import nothing new in the test modules.

**[AMENDMENT C constraint]** `two_cycles` was never moved, so this instruction stands. But the
move must not disturb `purge_ledger()`, `cleanup_applications`, `cleanup_opening_inventory`,
or any of their call sites. Do not add a second purge path; if `two_cycles` needs ledger
cleanup, call the scoped `purge_ledger(db, cycle_ids=[...])` from Task 24.

**Do not** weaken `resolve_production_cycle_for_date` to make old tests pass — the rejection is the
feature.

- [ ] **Step 10: Commit**

```bash
git add backend/app/database/models.py backend/alembic/versions \
        backend/app/services/transaction.py backend/app/schemas/transaction.py \
        backend/tests/test_transaction_cycle_resolution.py backend/tests/conftest.py \
        backend/tests/test_transactions.py backend/tests/test_transaction_date_filter.py
git commit -m "feat: attribute sales to a production cycle by date

Half-open [start, end) date matching, rejecting dates that match no
cycle or more than one rather than silently assigning the latest.
Column is nullable and never backfilled.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 9: Inventory derivation service + `GET /api/inventory`

**Requirements covered:** "Derive available stock from opening inventory + all applied production - all sales"; "IMPORTANT DISTINCTION: produced quantity for the current 7-day cycle / sold quantity for the current 7-day cycle / actual available inventory across all cycles"; "Preserve unsold stock across production cycles while resetting cycle-specific production and sales totals"; "Prevent negative available stock."

**Files:**
- Create: `backend/app/services/inventory.py`
- Create: `backend/app/schemas/inventory.py`
- Create: `backend/app/routers/inventory.py`
- Modify: `backend/main.py` (import + `include_router`)
- Test: `backend/tests/test_inventory.py` (new)

**Interfaces:**
- Consumes: `get_opening_quantities`, `is_stock_validation_enabled` (Task 2); `get_total_produced_by_product`, `get_cycle_produced_by_product` (Task 4); `get_latest_production_cycle` (existing).
- Produces: every symbol under `services/inventory.py` in the interface reference, plus `InventoryOverviewResponse`, `ProductInventoryResponse`.

`get_inventory_overview` returns exactly:

```python
{
    "cycle_id": int | None,
    "cycle_start_date": datetime | None,
    "cycle_end_date": datetime | None,
    "stock_validation_enabled": bool,
    "products": [
        {
            "product_id": int,
            "product_name": str,
            "opening_quantity": Decimal,
            "total_produced": Decimal,
            "total_sold": Decimal,
            "available_stock": Decimal,
            "cycle_produced": Decimal,
            "cycle_sold": Decimal,
        },
        ...
    ],
}
```

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_inventory.py`:

```python
from datetime import datetime
from decimal import Decimal

from app.database.models import OpeningInventoryItem, OpeningInventorySet


def _review_opening(db, product_id, quantity):
    inventory_set = OpeningInventorySet(
        set_number=f"OI-INV{product_id}",
        status="REVIEWED",
        effective_date=datetime(2026, 10, 1),
        reviewed_at=datetime(2026, 10, 1),
    )

    db.add(inventory_set)
    db.flush()

    db.add(
        OpeningInventoryItem(
            opening_inventory_set_id=inventory_set.id,
            product_id=product_id,
            quantity=Decimal(str(quantity)),
        )
    )

    db.commit()

    return inventory_set


def test_available_stock_is_opening_plus_produced_minus_sold(
    db, cleanup_opening_inventory, cleanup_applications,
    optimization_cycle, test_products,
):
    """
    The one formula the whole feature rests on. Opening inventory is a
    real starting balance - not zero - so it must appear in the sum.
    """

    from app.services.inventory import get_available_stock_for_product
    from app.services.production_application import (
        save_production_application,
    )
    from app.database.models import OptimizationRun, SalesTransaction

    product = test_products[0]

    _review_opening(db, product.id, 4)

    run = OptimizationRun(
        production_cycle_id=optimization_cycle.id,
        started_at=datetime(2026, 10, 30, 9, 0),
        status="OPTIMAL",
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    save_production_application(
        db,
        optimization_cycle.id,
        run.id,
        {product.id: Decimal("10")},
        [],
    )
    db.commit()

    sale = SalesTransaction(
        transaction_number="TRX-INV0001",
        product_id=product.id,
        production_cycle_id=optimization_cycle.id,
        transaction_date=datetime(2026, 10, 31),
        quantity_produced=Decimal("10"),
        quantity=Decimal("5"),
        unit_price=Decimal("100"),
        total_sales=Decimal("500"),
        production_cost=Decimal("0"),
        unit_profit=Decimal("100"),
        total_profit=Decimal("500"),
    )

    db.add(sale)
    db.commit()

    try:
        # 4 opening + 10 produced - 5 sold
        assert get_available_stock_for_product(
            db, product.id,
        ) == Decimal("9")

    finally:
        db.delete(sale)
        db.commit()


def test_stock_is_zero_based_on_opening_when_nothing_else_exists(
    db, cleanup_opening_inventory, cleanup_applications, test_products,
):
    """
    Opening inventory alone IS available stock before any production
    or sales - the explicit rejection of "start at zero".
    """

    from app.services.inventory import get_available_stock_for_product

    product = test_products[0]

    _review_opening(db, product.id, 7)

    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("7")


def test_unreviewed_opening_inventory_does_not_count(
    db, cleanup_opening_inventory, cleanup_applications, test_products,
):
    from app.services.inventory import get_available_stock_for_product

    product = test_products[0]

    inventory_set = OpeningInventorySet(
        set_number="OI-INVDRAFT",
        status="DRAFT",
        effective_date=datetime(2026, 10, 1),
    )

    db.add(inventory_set)
    db.flush()

    db.add(
        OpeningInventoryItem(
            opening_inventory_set_id=inventory_set.id,
            product_id=product.id,
            quantity=Decimal("99"),
        )
    )

    db.commit()

    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("0")


def test_cycle_totals_reset_while_stock_carries_over(
    db, cleanup_opening_inventory, cleanup_applications,
    optimization_cycle, test_products,
):
    """
    Requirement 5, exactly: a new cycle starts its produced and sold
    totals at zero while actual available inventory is untouched.
    """

    from app.database.models import (
        OptimizationRun,
        ProductionCycle,
        SalesTransaction,
    )
    from app.services.inventory import (
        get_available_stock_for_product,
        get_cycle_sold_by_product,
    )
    from app.services.production_application import (
        get_cycle_produced_by_product,
        save_production_application,
    )

    product = test_products[0]

    run = OptimizationRun(
        production_cycle_id=optimization_cycle.id,
        started_at=datetime(2026, 10, 30, 9, 0),
        status="OPTIMAL",
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    save_production_application(
        db,
        optimization_cycle.id,
        run.id,
        {product.id: Decimal("10")},
        [],
    )
    db.commit()

    sale = SalesTransaction(
        transaction_number="TRX-INV0002",
        product_id=product.id,
        production_cycle_id=optimization_cycle.id,
        transaction_date=datetime(2026, 10, 31),
        quantity_produced=Decimal("10"),
        quantity=Decimal("4"),
        unit_price=Decimal("100"),
        total_sales=Decimal("400"),
        production_cost=Decimal("0"),
        unit_profit=Decimal("100"),
        total_profit=Decimal("400"),
    )

    db.add(sale)
    db.commit()

    next_cycle = ProductionCycle(
        cycle_date=datetime(2026, 12, 20),
        start_date=datetime(2026, 12, 20),
        end_date=datetime(2026, 12, 27),
        status="OPEN",
    )

    db.add(next_cycle)
    db.commit()
    db.refresh(next_cycle)

    try:
        # Cycle-scoped figures for the NEW cycle are empty...
        assert get_cycle_produced_by_product(
            db, next_cycle.id,
        ).get(product.id, Decimal("0")) == Decimal("0")

        assert get_cycle_sold_by_product(
            db, next_cycle.id,
        ).get(product.id, Decimal("0")) == Decimal("0")

        # ...while the unsold units survive the boundary.
        assert get_available_stock_for_product(
            db, product.id,
        ) == Decimal("6")

    finally:
        db.delete(sale)
        db.delete(next_cycle)
        db.commit()


def test_unattributed_produced_draws_down_within_a_cycle(
    db, cleanup_opening_inventory, cleanup_applications,
    optimization_cycle, test_products,
):
    """
    The rule that keeps the forecast chart honest: the first sale after
    an apply carries the newly produced units, a later sale in the same
    cycle carries zero, so the cycle's quantity_produced sum can never
    exceed what the cycle actually produced.
    """

    from app.database.models import OptimizationRun, SalesTransaction
    from app.services.inventory import get_unattributed_produced
    from app.services.production_application import (
        save_production_application,
    )

    product = test_products[0]

    run = OptimizationRun(
        production_cycle_id=optimization_cycle.id,
        started_at=datetime(2026, 10, 30, 9, 0),
        status="OPTIMAL",
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    save_production_application(
        db,
        optimization_cycle.id,
        run.id,
        {product.id: Decimal("10")},
        [],
    )
    db.commit()

    assert get_unattributed_produced(
        db, optimization_cycle.id, product.id,
    ) == Decimal("10")

    sale = SalesTransaction(
        transaction_number="TRX-INV0003",
        product_id=product.id,
        production_cycle_id=optimization_cycle.id,
        transaction_date=datetime(2026, 10, 31),
        quantity_produced=Decimal("10"),
        quantity=Decimal("3"),
        unit_price=Decimal("100"),
        total_sales=Decimal("300"),
        production_cost=Decimal("0"),
        unit_profit=Decimal("100"),
        total_profit=Decimal("300"),
    )

    db.add(sale)
    db.commit()

    try:
        assert get_unattributed_produced(
            db, optimization_cycle.id, product.id,
        ) == Decimal("0")

    finally:
        db.delete(sale)
        db.commit()


def test_unattributed_produced_never_goes_negative(
    db, cleanup_opening_inventory, cleanup_applications,
    optimization_cycle, test_products,
):
    """
    A legacy row with a hand-typed quantity_produced larger than the
    cycle ever produced must floor at zero, not hand back a negative
    auto-fill value.
    """

    from app.database.models import SalesTransaction
    from app.services.inventory import get_unattributed_produced

    product = test_products[0]

    sale = SalesTransaction(
        transaction_number="TRX-INV0004",
        product_id=product.id,
        production_cycle_id=optimization_cycle.id,
        transaction_date=datetime(2026, 10, 31),
        quantity_produced=Decimal("500"),
        quantity=Decimal("1"),
        unit_price=Decimal("100"),
        total_sales=Decimal("100"),
        production_cost=Decimal("0"),
        unit_profit=Decimal("100"),
        total_profit=Decimal("100"),
    )

    db.add(sale)
    db.commit()

    try:
        assert get_unattributed_produced(
            db, optimization_cycle.id, product.id,
        ) == Decimal("0")

    finally:
        db.delete(sale)
        db.commit()


def test_inventory_endpoint_reports_all_three_figures(
    client, db, cleanup_opening_inventory, cleanup_applications,
    optimization_cycle, test_products,
):
    product = test_products[0]

    _review_opening(db, product.id, 2)

    response = client.get("/api/inventory")

    assert response.status_code == 200

    payload = response.json()

    assert payload["stock_validation_enabled"] is True
    assert payload["cycle_id"] is not None

    row = next(
        item for item in payload["products"]
        if item["product_id"] == product.id
    )

    for field in (
        "opening_quantity",
        "total_produced",
        "total_sold",
        "available_stock",
        "cycle_produced",
        "cycle_sold",
    ):
        assert field in row

    assert Decimal(row["opening_quantity"]) == Decimal("2")
    assert Decimal(row["available_stock"]) == Decimal("2")


def test_inventory_requires_authentication(unauthenticated_client):
    assert unauthenticated_client.get(
        "/api/inventory"
    ).status_code == 401
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_inventory.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.services.inventory'`.

- [ ] **Step 3: Write the service**

Create `backend/app/services/inventory.py`:

```python
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Product, SalesTransaction
from app.services.opening_inventory import (
    get_opening_quantities,
    is_stock_validation_enabled,
)
from app.services.production import get_latest_production_cycle
from app.services.production_application import (
    get_cycle_produced_by_product,
    get_total_produced_by_product,
)


def lock_product_for_stock_update(
    db: Session,
    product_id: int,
) -> None:
    """
    Serialises stock-changing work for ONE product.

    Available stock is derived, not stored, so there is no row whose
    own constraint could reject an oversell - two concurrent sales
    would each read the same stock figure, each find room, and both
    commit. Locking the product row makes the read-check-write
    sequence atomic with respect to any other request touching the
    same product, which is the only thing that actually prevents it.

    Takes the lock on `products` rather than on the sales rows because
    the quantity being protected is a SUM over rows that do not exist
    yet - there is nothing in sales_transactions to lock. The lock is
    held until the caller's commit or rollback.

    Different products never block each other: two sales of different
    furniture items take different locks and proceed in parallel.
    """

    db.execute(
        select(Product.id)
        .where(Product.id == product_id)
        .with_for_update()
    ).scalar_one_or_none()


def get_total_sold_by_product(db: Session) -> dict[int, Decimal]:
    """
    product_id -> units sold across ALL time, every cycle included and
    rows with a NULL production_cycle_id included too. Deliberately
    never cycle-filtered: a sale reduced real stock whenever it
    happened, so excluding any sale here would overstate what is on
    hand.
    """

    rows = db.execute(
        select(
            SalesTransaction.product_id,
            func.sum(SalesTransaction.quantity),
        ).group_by(SalesTransaction.product_id)
    ).all()

    return {
        product_id: total
        for product_id, total in rows
        if total is not None
    }


def get_cycle_sold_by_product(
    db: Session,
    cycle_id: int,
) -> dict[int, Decimal]:
    """
    product_id -> units sold within ONE cycle. Resets for a new cycle
    (no rows yet) while get_total_sold_by_product keeps growing - the
    sold half of "cycle totals reset, stock carries over". Rows with a
    NULL production_cycle_id are excluded here by construction, which
    is correct: they belong to no cycle.
    """

    rows = db.execute(
        select(
            SalesTransaction.product_id,
            func.sum(SalesTransaction.quantity),
        )
        .where(SalesTransaction.production_cycle_id == cycle_id)
        .group_by(SalesTransaction.product_id)
    ).all()

    return {
        product_id: total
        for product_id, total in rows
        if total is not None
    }


def get_available_stock(db: Session) -> dict[int, Decimal]:
    """
    product_id -> units on hand right now:

        opening (reviewed declaration) + all applied production
        - all sales, across every cycle

    DERIVED on every read, never stored. A stored counter would have
    to be reversed correctly on every transaction edit and delete
    (both of which the API supports) and would drift the first time a
    reversal was missed; a sum cannot drift. Products absent from every
    source resolve to zero via the union below rather than being
    omitted, so a caller can always look up any product id.

    Floored at zero: stock can only go negative through pre-existing
    data (a legacy sale of stock the ledger never recorded), and
    reporting a negative on-hand figure would be a lie about physical
    goods. The sales-validation path in transaction.py is what keeps
    NEW sales from creating that state in the first place.
    """

    opening = get_opening_quantities(db)
    produced = get_total_produced_by_product(db)
    sold = get_total_sold_by_product(db)

    product_ids = (
        set(opening) | set(produced) | set(sold)
    )

    return {
        product_id: max(
            Decimal("0"),
            opening.get(product_id, Decimal("0"))
            + produced.get(product_id, Decimal("0"))
            - sold.get(product_id, Decimal("0")),
        )
        for product_id in product_ids
    }


def get_available_stock_for_product(
    db: Session,
    product_id: int,
) -> Decimal:
    """
    Single-product convenience over get_available_stock. A product
    with no opening balance, no production and no sales correctly
    resolves to zero rather than raising.
    """

    return get_available_stock(db).get(
        product_id,
        Decimal("0"),
    )


def get_unattributed_produced(
    db: Session,
    cycle_id: int,
    product_id: int,
) -> Decimal:
    """
    Newly applied production in this cycle that no transaction has
    recorded yet:

        cycle produced - sum of quantity_produced already recorded
        on this cycle's transactions for this product

    This is what a new transaction's quantity_produced is auto-filled
    with, and it is a DRAWDOWN, not a running total: the first sale
    after an apply carries the newly produced units, later sales in
    the same cycle carry zero. That guarantees the cycle's
    quantity_produced sum equals what the cycle actually produced, so
    the column can never overstate production however many
    transactions someone happens to record.

    (R1) Demand Forecasting no longer reads this column for new
    production - forecasting.py::get_production_event_series reads
    the ledger directly - so this invariant now protects the stored
    column, per-transaction production cost, and Transaction
    History, rather than the chart.

    Explicitly NOT available stock. Available stock spans every cycle
    and includes opening inventory; using it here would report units
    produced in earlier cycles as if they were produced now.

    Floored at zero so a legacy row whose hand-typed quantity_produced
    exceeds what the cycle produced yields 0 rather than a negative
    auto-fill.
    """

    produced = get_cycle_produced_by_product(db, cycle_id).get(
        product_id,
        Decimal("0"),
    )

    attributed = db.scalar(
        select(
            func.coalesce(
                func.sum(SalesTransaction.quantity_produced),
                0,
            )
        ).where(
            SalesTransaction.production_cycle_id == cycle_id,
            SalesTransaction.product_id == product_id,
        )
    ) or Decimal("0")

    return max(Decimal("0"), produced - attributed)


def get_inventory_overview(db: Session) -> dict:
    """
    Every figure a stock-aware screen needs, for every active product,
    keeping the three distinct quantities the spec calls out visibly
    separate: cycle produced, cycle sold, and all-cycles available
    stock.
    """

    cycle = get_latest_production_cycle(db)

    opening = get_opening_quantities(db)
    produced = get_total_produced_by_product(db)
    sold = get_total_sold_by_product(db)
    stock = get_available_stock(db)

    cycle_produced = (
        get_cycle_produced_by_product(db, cycle.id)
        if cycle is not None
        else {}
    )

    cycle_sold = (
        get_cycle_sold_by_product(db, cycle.id)
        if cycle is not None
        else {}
    )

    products = db.scalars(
        select(Product)
        .where(Product.is_active.is_(True))
        .order_by(Product.id)
    ).all()

    return {
        "cycle_id": cycle.id if cycle is not None else None,
        "cycle_start_date": (
            cycle.start_date if cycle is not None else None
        ),
        "cycle_end_date": (
            cycle.end_date if cycle is not None else None
        ),
        "stock_validation_enabled": (
            is_stock_validation_enabled(db)
        ),
        "products": [
            {
                "product_id": product.id,
                "product_name": product.name,
                "opening_quantity": opening.get(
                    product.id, Decimal("0"),
                ),
                "total_produced": produced.get(
                    product.id, Decimal("0"),
                ),
                "total_sold": sold.get(
                    product.id, Decimal("0"),
                ),
                "available_stock": stock.get(
                    product.id, Decimal("0"),
                ),
                "cycle_produced": cycle_produced.get(
                    product.id, Decimal("0"),
                ),
                "cycle_sold": cycle_sold.get(
                    product.id, Decimal("0"),
                ),
            }
            for product in products
        ],
    }
```

- [ ] **Step 4: Write the schemas**

Create `backend/app/schemas/inventory.py`:

```python
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ProductInventoryResponse(BaseModel):
    product_id: int
    product_name: str

    # Declared opening balance from the REVIEWED opening inventory
    # set; 0 when none was declared for this product.
    opening_quantity: Decimal

    # All-cycles ledger totals - the two halves of available_stock
    # alongside opening_quantity.
    total_produced: Decimal
    total_sold: Decimal

    # opening + total_produced - total_sold, floored at zero. The
    # actual on-hand figure, spanning every cycle.
    available_stock: Decimal

    # CURRENT cycle only. These two reset to zero when a new cycle
    # starts; available_stock above does not.
    cycle_produced: Decimal
    cycle_sold: Decimal


class InventoryOverviewResponse(BaseModel):
    # Null when no production cycle exists yet, in which case every
    # cycle_* figure above is 0.
    cycle_id: int | None
    cycle_start_date: datetime | None
    cycle_end_date: datetime | None

    # False until an opening inventory set has been reviewed. While
    # false, sales are NOT validated against stock - the client must
    # say so rather than implying the figures are being enforced.
    stock_validation_enabled: bool

    products: list[ProductInventoryResponse]
```

- [ ] **Step 5: Write the router and register it**

Create `backend/app/routers/inventory.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.inventory import InventoryOverviewResponse
from app.services.auth import get_current_user
from app.services.inventory import get_inventory_overview


router = APIRouter(
    prefix="/api/inventory",
    tags=["Inventory"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=InventoryOverviewResponse,
    summary="Available stock and cycle production/sales totals",
)
def get_inventory(
    db: Session = Depends(get_db),
):
    return get_inventory_overview(db)
```

In `backend/main.py`, add `from app.routers.inventory import router as inventory_router` to the
import block and `app.include_router(inventory_router)` after the opening inventory router.

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_inventory.py -v
```

Expected: 8 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/inventory.py backend/app/schemas/inventory.py \
        backend/app/routers/inventory.py backend/main.py \
        backend/tests/test_inventory.py
git commit -m "feat: derive available stock and cycle totals

opening + all applied production - all sales, derived on read and
floored at zero, with cycle-scoped produced/sold reported separately
so a new cycle resets totals without resetting stock.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 10: Transaction create — auto-filled Quantity Produced, stock validation, product lock

**Requirements covered:** "After a production allocation is successfully applied, the corresponding furniture product's produced quantity should automatically be reflected in Transaction History when adding a transaction... Do not require users to manually enter or synchronize the produced quantity"; "Quantity Produced: read-only"; "When a sales transaction is recorded... automatically deduct the sold quantity from its available stock... Prevent negative available stock. Validate that a sale does not exceed available inventory"; "Prevent overselling under concurrent requests"; "Do not use available stock as newly produced quantity in SalesTransaction.quantity_produced or inflate the forecast chart"; "Require opening inventory setup to be completed and reviewed before enabling stock-based sales validation."

**Contract change:** `SalesTransactionCreate.quantity_produced` becomes **optional and server-computed**. A client-sent value is ignored, not rejected, so the existing frontend and any script keep working while the server becomes the only source of the figure. `Field(gt=0)` also has to go: the drawdown rule makes `0` a legitimate value for the second sale in a cycle.

**Files:**
- Modify: `backend/app/schemas/transaction.py` (`SalesTransactionCreate`)
- Modify: `backend/app/services/transaction.py::create_transaction`
- Test: `backend/tests/test_transaction_stock.py` (new)

**Interfaces:**
- Consumes: `resolve_production_cycle_for_date` (Task 8); `lock_product_for_stock_update`, `get_available_stock_for_product`, `get_unattributed_produced` (Task 9); `is_stock_validation_enabled` (Task 2).
- Produces: `create_transaction(db, transaction_data) -> SalesTransaction` — same signature; now raises `ValueError` for an oversell and ignores a client-sent `quantity_produced`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_transaction_stock.py`:

```python
from datetime import datetime
from decimal import Decimal

from app.database.models import (
    OpeningInventoryItem,
    OpeningInventorySet,
    OptimizationRun,
    SalesTransaction,
)
from app.services.production_application import (
    save_production_application,
)


def _review_opening(db, product_id, quantity, suffix="A"):
    inventory_set = OpeningInventorySet(
        set_number=f"OI-STK{suffix}",
        status="REVIEWED",
        effective_date=datetime(2026, 10, 1),
        reviewed_at=datetime(2026, 10, 1),
    )

    db.add(inventory_set)
    db.flush()

    db.add(
        OpeningInventoryItem(
            opening_inventory_set_id=inventory_set.id,
            product_id=product_id,
            quantity=Decimal(str(quantity)),
        )
    )

    db.commit()


def _apply_production(db, cycle_id, product_id, quantity):
    run = OptimizationRun(
        production_cycle_id=cycle_id,
        started_at=datetime(2026, 10, 30, 9, 0),
        status="OPTIMAL",
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    save_production_application(
        db,
        cycle_id,
        run.id,
        {product_id: Decimal(str(quantity))},
        [],
    )
    db.commit()


def _sale_payload(product_id, day, quantity, **overrides):
    payload = {
        "product_id": product_id,
        "transaction_date": f"2026-10-{day:02d}T00:00:00",
        "quantity": quantity,
        "unit_price": 100,
        "production_cost": 0,
    }
    payload.update(overrides)

    return payload


def _cleanup_sales(db, product_id):
    db.query(SalesTransaction).filter(
        SalesTransaction.product_id == product_id
    ).delete(synchronize_session=False)
    db.commit()


def test_quantity_produced_is_auto_filled_from_applied_production(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    Requirement 2: the produced figure comes from the ledger, not from
    the user. A value sent by the client is ignored rather than
    rejected, so older clients keep working while the server stays the
    only source of truth.
    """

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "B")
    _apply_production(db, transaction_cycle.id, product.id, 10)

    response = client.post(
        "/api/transactions",
        json=_sale_payload(
            product.id, 31, 4, quantity_produced=999,
        ),
    )

    assert response.status_code == 201, response.text
    assert Decimal(response.json()["quantity_produced"]) == (
        Decimal("10")
    )

    _cleanup_sales(db, product.id)


def test_a_second_sale_in_the_same_cycle_records_zero_produced(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    The anti-inflation rule. Two sales after one apply of 10 must sum
    to 10 produced, not 20 - otherwise Demand Forecasting's produced
    series grows with the number of transactions recorded rather than
    with actual production.
    """

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "C")
    _apply_production(db, transaction_cycle.id, product.id, 10)

    first = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 3),
    )
    second = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 2),
    )

    assert first.status_code == 201
    assert second.status_code == 201

    assert Decimal(first.json()["quantity_produced"]) == (
        Decimal("10")
    )
    assert Decimal(second.json()["quantity_produced"]) == (
        Decimal("0")
    )

    total_produced = db.query(
        SalesTransaction.quantity_produced
    ).filter(
        SalesTransaction.product_id == product.id,
        SalesTransaction.production_cycle_id
        == transaction_cycle.id,
    ).all()

    assert sum(
        row[0] for row in total_produced
    ) == Decimal("10")

    _cleanup_sales(db, product.id)


def test_quantity_produced_is_never_available_stock(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    Explicitly forbidden by the spec. With 40 units of opening stock
    and only 6 newly produced, the recorded produced figure must be 6.
    """

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 40, "D")
    _apply_production(db, transaction_cycle.id, product.id, 6)

    response = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 1),
    )

    assert Decimal(response.json()["quantity_produced"]) == (
        Decimal("6")
    )

    _cleanup_sales(db, product.id)


def test_a_sale_exceeding_available_stock_is_rejected(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "E")
    _apply_production(db, transaction_cycle.id, product.id, 10)

    response = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 11),
    )

    assert response.status_code == 400

    detail = response.json()["detail"].lower()

    assert "available" in detail
    assert "10" in response.json()["detail"]

    assert (
        db.query(SalesTransaction)
        .filter(SalesTransaction.product_id == product.id)
        .count()
        == 0
    )

    _cleanup_sales(db, product.id)


def test_a_sale_of_exactly_the_available_stock_succeeds(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    from app.services.inventory import (
        get_available_stock_for_product,
    )

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "F")
    _apply_production(db, transaction_cycle.id, product.id, 10)

    response = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 10),
    )

    assert response.status_code == 201

    db.expire_all()

    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("0")

    _cleanup_sales(db, product.id)


def test_the_full_day_1_3_5_scenario(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    The spec's worked example end to end: apply 10 -> stock 10;
    sell 5 -> stock 5; apply 10 again -> stock 15. This is the
    regression test for the overwrite bug that motivated the whole
    plan.
    """

    from app.services.inventory import (
        get_available_stock_for_product,
    )

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "G")

    _apply_production(db, transaction_cycle.id, product.id, 10)
    db.expire_all()
    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("10")

    assert client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 5),
    ).status_code == 201

    db.expire_all()
    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("5")

    _apply_production(db, transaction_cycle.id, product.id, 10)
    db.expire_all()
    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("15")

    _cleanup_sales(db, product.id)


# [INVERTED BY AMENDMENT A - Task 23 rewrites this test.]
# The scenario stays; the expected outcome flips. With no complete
# REVIEWED opening inventory the sale must be REFUSED (409), not
# accepted with status 201. Rename to
# test_sales_are_refused_before_a_complete_opening_review and assert
# the refusal plus that no SalesTransaction row was written. The
# docstring and assertion below describe the REJECTED soft-gate
# behaviour; do not implement them as written.
def test_stock_validation_is_skipped_before_opening_review(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    The gate from the opposite side: with no reviewed opening
    inventory, a sale of stock the system does not know about must
    still be accepted. Enforcing against an unconfirmed balance would
    block the shop from recording real sales during setup.
    """

    product = test_products[0]
    _cleanup_sales(db, product.id)

    response = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 25),
    )

    assert response.status_code == 201

    _cleanup_sales(db, product.id)


def test_concurrent_sales_cannot_oversell(
    db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    Two sessions, each selling the entire stock, committed in an
    interleaved order. The product row lock must make the second one
    block until the first commits and then see the updated figure -
    without it, both read 10, both pass, and stock goes to -10.
    """

    from app.database.connection import SessionLocal
    from app.schemas.transaction import SalesTransactionCreate
    from app.services.inventory import (
        get_available_stock_for_product,
    )
    from app.services.transaction import create_transaction

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "H")
    _apply_production(db, transaction_cycle.id, product.id, 10)

    payload = SalesTransactionCreate(
        product_id=product.id,
        transaction_date=datetime(2026, 10, 31),
        quantity=Decimal("10"),
        unit_price=Decimal("100"),
        production_cost=Decimal("0"),
    )

    first_session = SessionLocal()
    second_session = SessionLocal()

    try:
        create_transaction(first_session, payload)

        # The second session now sees stock 0 and must refuse.
        try:
            create_transaction(second_session, payload)
            committed_twice = True
        except ValueError:
            committed_twice = False

        assert committed_twice is False

        db.expire_all()

        assert get_available_stock_for_product(
            db, product.id,
        ) == Decimal("0")

    finally:
        first_session.close()
        second_session.close()
        _cleanup_sales(db, product.id)
```

Add the shared cycle fixture to `backend/tests/conftest.py` (the transaction tests need a cycle
whose window contains October 2026 dates).

**[AMENDMENT C constraint]** `transaction_cycle` does not exist yet, so this instruction stands.
Keep it **function-scoped** exactly as written — a module- or session-scoped fixture holding
ledger rows would be wiped by another test's function-scoped purge. Its teardown must use the
scoped `purge_ledger(db, cycle_ids=[cycle.id])` from Task 24, never a blanket purge:

```python
@pytest.fixture
def transaction_cycle(db):
    """
    A cycle covering late October 2026, so transaction tests can use
    real dates that resolve to a real cycle - required since
    resolve_production_cycle_for_date rejects dates outside every
    cycle. Half-open [start, end), so Oct 31 is inside.
    """

    cycle = ProductionCycle(
        cycle_date=datetime(2026, 10, 25),
        start_date=datetime(2026, 10, 25),
        end_date=datetime(2026, 11, 1),
        status="OPEN",
    )

    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    yield cycle

    db.query(SalesTransaction).filter(
        SalesTransaction.production_cycle_id == cycle.id
    ).delete(synchronize_session=False)
    db.delete(cycle)
    db.commit()
```

Add `SalesTransaction` to `conftest.py`'s model import block.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_transaction_stock.py -v
```

Expected: failures — `quantity_produced` is required by the schema (422), and no stock validation
exists so the oversell tests get 201.

- [ ] **Step 3: Make `quantity_produced` server-computed in the create schema**

In `backend/app/schemas/transaction.py`, replace `SalesTransactionCreate`:

```python
class SalesTransactionCreate(BaseModel):
    product_id: int
    transaction_date: datetime

    # SERVER-COMPUTED - app/services/transaction.py::create_transaction
    # overwrites whatever arrives here with
    # inventory.py::get_unattributed_produced for this product in the
    # transaction's own cycle. Accepted-and-ignored rather than
    # forbidden so existing clients and scripts that still send it keep
    # working; optional so new clients can simply omit it.
    #
    # gt=0 was deliberately dropped: under the drawdown rule the
    # SECOND sale in a cycle legitimately records 0 newly-produced
    # units, which is what keeps the per-cycle produced sum equal to
    # actual production instead of multiplying with the number of
    # transactions recorded.
    quantity_produced: Decimal | None = Field(
        default=None,
        ge=0,
    )

    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(gt=0)
    # Per-unit production cost - app/services/transaction.py::
    # calculate_transaction_values multiplies this by quantity_produced
    # before storing/returning it as the TOTAL production_cost (see
    # SalesTransactionResponse.production_cost below).
    production_cost: Decimal = Field(ge=0)
```

- [ ] **Step 4: Rewrite `create_transaction`**

In `backend/app/services/transaction.py`, extend the imports:

```python
from app.services.inventory import (
    get_available_stock_for_product,
    get_unattributed_produced,
    lock_product_for_stock_update,
)
from app.services.opening_inventory import (
    is_stock_validation_enabled,
)
```

**Circular-import note:** `services/inventory.py` imports from `services/production_application.py`
and `services/opening_inventory.py`, and neither imports `services/transaction.py` — so this is
acyclic. If a future change makes it circular, move these two imports inside the function body
rather than restructuring either module.

Replace `create_transaction`:

```python
def create_transaction(
    db: Session,
    transaction_data: SalesTransactionCreate,
) -> SalesTransaction:
    product = db.get(
        Product,
        transaction_data.product_id,
    )

    if product is None:
        raise ValueError("Product not found")

    if not product.is_active:
        raise ValueError(
            "Cannot create transaction for inactive product"
        )

    # Rejects a date that belongs to no cycle (or to more than one)
    # instead of attributing the sale to the latest cycle - a sale in
    # the wrong cycle silently corrupts that cycle's reported sales.
    production_cycle = resolve_production_cycle_for_date(
        db,
        transaction_data.transaction_date,
    )

    # Serialises every stock-changing request for THIS product.
    # Available stock is a derived SUM, so there is no row constraint
    # that could reject an oversell: without this lock two concurrent
    # sales both read the same figure, both find room, and both
    # commit. Taken BEFORE the stock figure is read, and held until
    # this function's commit or rollback.
    lock_product_for_stock_update(db, product.id)

    # The gate: enforcing against an opening balance nobody has
    # reviewed would reject real sales of stock the ledger does not
    # know about yet. Until then sales are recorded unvalidated, which
    # is the deliberate, documented behaviour.
    if is_stock_validation_enabled(db):
        available_stock = get_available_stock_for_product(
            db,
            product.id,
        )

        if transaction_data.quantity > available_stock:
            raise ValueError(
                f"Cannot sell {transaction_data.quantity} units of "
                f"{product.name} - only {available_stock} units are "
                "available. Apply a production plan to produce more, "
                "or reduce the quantity sold."
            )

    # Server-computed, ignoring any client-sent value. This is the
    # production NEWLY applied in this cycle that no transaction has
    # claimed yet - a drawdown, so the first sale after an apply
    # carries the new units and later sales in the same cycle carry 0.
    # Never available stock: that spans every cycle and includes
    # opening inventory, so using it here would report old units as
    # newly produced and overstate what this cycle produced. (R1: the
    # forecast chart reads production from the ledger, not from this
    # column, but the column must still not overstate production -
    # it drives this transaction's production cost.)
    quantity_produced = get_unattributed_produced(
        db,
        production_cycle.id,
        product.id,
    )

    values = calculate_transaction_values(
        quantity_produced,
        transaction_data.quantity,
        transaction_data.unit_price,
        transaction_data.production_cost,
    )

    transaction = SalesTransaction(
        transaction_number=generate_transaction_number(db),
        product_id=transaction_data.product_id,
        production_cycle_id=production_cycle.id,
        transaction_date=transaction_data.transaction_date,
        quantity_produced=quantity_produced,
        quantity=transaction_data.quantity,
        unit_price=transaction_data.unit_price,
        total_sales=values["total_sales"],
        production_cost=values["production_cost"],
        unit_profit=values["unit_profit"],
        total_profit=values["total_profit"],
    )

    try:
        db.add(transaction)
        db.commit()
        db.refresh(transaction)

        return transaction

    except Exception:
        db.rollback()
        raise
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_transaction_stock.py -v
```

Expected: 8 passed.

- [ ] **Step 6: Repair the existing transaction tests**

```bash
cd backend && python -m pytest tests/test_transactions.py -v
```

`test_create_transaction_rejects_invalid_quantity_produced`
(`tests/test_transactions.py:309`) asserts a 422 for a non-positive `quantity_produced`. That
contract is intentionally gone — the field is server-computed. Replace that test with:

```python
def test_create_transaction_ignores_a_client_sent_quantity_produced(
    client, db, transaction_cycle, test_products,
):
    """
    quantity_produced is server-computed now (see
    app/schemas/transaction.py::SalesTransactionCreate). A client-sent
    value must be ignored rather than rejected, so existing callers
    keep working - the old "reject a non-positive value" contract no
    longer applies because the client no longer owns the field.
    """

    response = client.post(
        "/api/transactions",
        json={
            "product_id": test_products[0].id,
            "transaction_date": "2026-10-31T00:00:00",
            "quantity_produced": 0,
            "quantity": 1,
            "unit_price": 100,
            "production_cost": 0,
        },
    )

    assert response.status_code == 201
```

`test_production_cost_uses_quantity_produced_not_sold`
(`tests/test_transactions.py:352`) asserts production cost scales with a *submitted*
`quantity_produced`. Rework it to apply production through the ledger first (reuse
`_apply_production` from `test_transaction_stock.py` — move it to `conftest.py` as a fixture-returning
helper if both files need it), then assert the cost scales with the auto-filled figure. Keep the
assertion's intent: cost follows produced, revenue follows sold.

**[AMENDMENT C constraint]** This instruction stands. `_apply_production` writes ledger rows, so
any fixture wrapping it must be **function-scoped** and must clean only its own rows via the
scoped `purge_ledger(...)` from Task 24.

- [ ] **Step 7: Verify the forecast suites are unaffected**

```bash
cd backend && python -m pytest tests/test_forecast.py tests/test_forecast_aggregation.py \
  tests/test_forecast_timeseries.py tests/test_forecast_history.py -q
```

Expected: all pass unchanged. `get_monthly_historical_demand` reads `SalesTransaction.quantity`,
which this task does not touch.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/transaction.py backend/app/services/transaction.py \
        backend/tests/test_transaction_stock.py backend/tests/conftest.py \
        backend/tests/test_transactions.py
git commit -m "feat: auto-fill produced quantity and validate sales against stock

quantity_produced is now server-computed from the ledger as a drawdown
of unclaimed cycle production, so the per-cycle sum equals actual
production. Sales above available stock are rejected, serialised on a
product row lock, and only once opening inventory has been reviewed.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 11: Transaction update and delete — stock validation and the zero-produced division fix

**Requirements covered:** "Reject sales exceeding available stock, including during transaction updates"; "Prevent negative available stock."

**Two real bugs this task closes:**
1. `update_transaction` has **no validation at all** and `routers/transactions.py`'s PATCH handler
   does not even catch `ValueError` — so a raised error would surface as a 500.
2. `update_transaction` computes `transaction.production_cost / transaction.quantity_produced`
   (`services/transaction.py`, in the `else` branch of the `"production_cost" in update_data`
   check). Task 10 makes `quantity_produced = 0` a normal stored value, so this is now a live
   `ZeroDivisionError` on any edit of a second-sale-in-a-cycle row.

**Files:**
- Modify: `backend/app/services/transaction.py::update_transaction`
- Modify: `backend/app/routers/transactions.py` (PATCH: catch `ValueError` → 400)
- Test: `backend/tests/test_transaction_stock.py` (append)

**Interfaces:**
- Consumes: Task 9's inventory helpers; Task 8's resolver.
- Produces: `update_transaction(db, transaction, transaction_data) -> SalesTransaction` — same signature, now raising `ValueError` for an oversell or an unmatched date.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_transaction_stock.py`:

```python
def test_raising_a_sale_above_available_stock_is_rejected(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    The update path needs the same guard as create: editing 4 up to 20
    oversells just as surely as recording 20 in the first place.
    """

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "I")
    _apply_production(db, transaction_cycle.id, product.id, 10)

    created = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 4),
    ).json()

    response = client.patch(
        f"/api/transactions/{created['id']}",
        json={"quantity": 20},
    )

    assert response.status_code == 400
    assert "available" in response.json()["detail"].lower()

    db.expire_all()

    assert db.get(
        SalesTransaction, created["id"],
    ).quantity == Decimal("4.0000")

    _cleanup_sales(db, product.id)


def test_an_update_does_not_double_count_its_own_quantity(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    The row being edited already counts against stock, so its own
    current quantity must be added back before the proposed quantity is
    checked. Without that, raising 4 to 10 against 10 units of
    production looks like a demand for 14 and is wrongly rejected.
    """

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "J")
    _apply_production(db, transaction_cycle.id, product.id, 10)

    created = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 4),
    ).json()

    response = client.patch(
        f"/api/transactions/{created['id']}",
        json={"quantity": 10},
    )

    assert response.status_code == 200, response.text

    db.expire_all()

    from app.services.inventory import (
        get_available_stock_for_product,
    )

    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("0")

    _cleanup_sales(db, product.id)


def test_lowering_a_sale_returns_stock(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    from app.services.inventory import (
        get_available_stock_for_product,
    )

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "K")
    _apply_production(db, transaction_cycle.id, product.id, 10)

    created = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 10),
    ).json()

    assert client.patch(
        f"/api/transactions/{created['id']}",
        json={"quantity": 3},
    ).status_code == 200

    db.expire_all()

    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("7")

    _cleanup_sales(db, product.id)


def test_deleting_a_sale_returns_stock(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    No code change needed - stock is derived, so removing the row
    removes its deduction automatically. Pinned because a stored
    counter would have silently got this wrong, and this test is what
    proves the derived design is doing its job.
    """

    from app.services.inventory import (
        get_available_stock_for_product,
    )

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "L")
    _apply_production(db, transaction_cycle.id, product.id, 10)

    created = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 6),
    ).json()

    assert client.delete(
        f"/api/transactions/{created['id']}",
    ).status_code == 204

    db.expire_all()

    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("10")

    _cleanup_sales(db, product.id)


def test_editing_a_zero_produced_row_does_not_crash(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    update_transaction reconstructs the per-unit production cost by
    dividing the stored total by quantity_produced. The drawdown rule
    makes 0 a normal stored value for the second sale in a cycle, so
    that division is a live ZeroDivisionError (a 500) without this fix.
    """

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "M")
    _apply_production(db, transaction_cycle.id, product.id, 10)

    client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 3),
    )

    second = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 2),
    ).json()

    assert Decimal(second["quantity_produced"]) == Decimal("0")

    response = client.patch(
        f"/api/transactions/{second['id']}",
        json={"quantity": 1},
    )

    assert response.status_code == 200, response.text
    assert Decimal(response.json()["production_cost"]) == (
        Decimal("0.00")
    )

    _cleanup_sales(db, product.id)


def test_moving_a_sale_to_a_date_outside_every_cycle_is_rejected(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    product = test_products[0]
    _cleanup_sales(db, product.id)

    created = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 1),
    ).json()

    response = client.patch(
        f"/api/transactions/{created['id']}",
        json={"transaction_date": "2029-01-01T00:00:00"},
    )

    assert response.status_code == 400
    assert "production cycle" in response.json()["detail"].lower()

    _cleanup_sales(db, product.id)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_transaction_stock.py -k "update or delet or zero or moving or raising or lowering or double" -v
```

Expected: the oversell-on-update tests return 200, the zero-produced edit returns a 500
(`ZeroDivisionError`), and the date test returns 200.

- [ ] **Step 3: Rewrite `update_transaction`**

In `backend/app/services/transaction.py`:

```python
def update_transaction(
    db: Session,
    transaction: SalesTransaction,
    transaction_data: SalesTransactionUpdate,
) -> SalesTransaction:
    """
    quantity_produced is deliberately NOT recomputed on update. It
    records what was newly produced at the moment the transaction was
    first recorded; re-deriving it now would reshuffle the drawdown
    across every row in the cycle and rewrite settled history. A
    client-sent quantity_produced is still accepted (the field remains
    on SalesTransactionUpdate) so a genuine correction stays possible,
    but it is not auto-filled.
    """

    update_data = transaction_data.model_dump(
        exclude_unset=True
    )

    quantity_produced = update_data.get(
        "quantity_produced",
        transaction.quantity_produced,
    )

    quantity = update_data.get(
        "quantity",
        transaction.quantity,
    )

    unit_price = update_data.get(
        "unit_price",
        transaction.unit_price,
    )

    transaction_date = update_data.get(
        "transaction_date",
        transaction.transaction_date,
    )

    # Re-resolve the cycle whenever the date moves, with the same
    # reject-rather-than-guess rule as create - an edited date that
    # belongs to no cycle must not leave the sale attributed to its
    # old one.
    #
    # (R1) A pre-rollout row is exempt. production_cycle_id IS NULL
    # is what marks it legacy, and the forecast uses that marker to
    # decide whose stored quantity_produced it still reports
    # (services/forecasting.py). Attributing such a row to a cycle
    # on an unrelated edit would silently drop its produced figure
    # off the chart - a rewrite of settled history, which the
    # Global Constraints forbid. It stays unattributed, exactly as
    # Task 8's migration left it.
    production_cycle_id = transaction.production_cycle_id

    if (
        "transaction_date" in update_data
        and transaction.production_cycle_id is not None
    ):
        production_cycle_id = resolve_production_cycle_for_date(
            db,
            transaction_date,
        ).id

    # Same lock, same reason, as create_transaction: the stock figure
    # about to be checked is a derived SUM with no row constraint
    # behind it.
    lock_product_for_stock_update(db, transaction.product_id)

    if is_stock_validation_enabled(db):
        product = db.get(Product, transaction.product_id)

        # This row's CURRENT quantity is already deducted from
        # available stock, so it has to be added back before the
        # proposed quantity is weighed - otherwise raising 4 to 10
        # against 10 produced units reads as a demand for 14 and is
        # wrongly rejected (the same self-double-counting trap
        # allocation.py::_validate_proposed_allocation_capacity
        # documents).
        available_stock = (
            get_available_stock_for_product(
                db,
                transaction.product_id,
            )
            + transaction.quantity
        )

        if quantity > available_stock:
            raise ValueError(
                f"Cannot sell {quantity} units of "
                f"{product.name if product else 'this product'} - "
                f"only {available_stock} units are available. Apply a "
                "production plan to produce more, or reduce the "
                "quantity sold."
            )

    # transaction.production_cost is the stored TOTAL (see
    # calculate_transaction_values). If this request doesn't send a
    # new production_cost, reconstruct the per-unit rate that produced
    # the currently-stored total using the quantity_produced that was
    # in effect when it was last saved - not the raw stored total
    # itself, which would otherwise be multiplied again below and
    # silently inflate the cost.
    #
    # quantity_produced == 0 is a NORMAL stored value since produced
    # quantities became a per-cycle drawdown (the second sale in a
    # cycle records 0), so the division has to be guarded: a zero
    # produced quantity means zero total cost, and any per-unit rate
    # reproduces that.
    if "production_cost" in update_data:
        production_cost_per_unit = update_data["production_cost"]
    elif transaction.quantity_produced:
        production_cost_per_unit = (
            transaction.production_cost
            / transaction.quantity_produced
        )
    else:
        production_cost_per_unit = Decimal("0")

    values = calculate_transaction_values(
        quantity_produced,
        quantity,
        unit_price,
        production_cost_per_unit,
    )

    for field, value in update_data.items():
        setattr(transaction, field, value)

    transaction.production_cycle_id = production_cycle_id
    transaction.total_sales = values["total_sales"]
    transaction.production_cost = values["production_cost"]
    transaction.unit_profit = values["unit_profit"]
    transaction.total_profit = values["total_profit"]

    try:
        db.commit()
        db.refresh(transaction)

        return transaction

    except Exception:
        db.rollback()
        raise
```

- [ ] **Step 4: Catch `ValueError` in the PATCH handler**

`backend/app/routers/transactions.py`'s `update_existing_transaction` currently returns
`update_transaction(...)` with no try/except, so every new `ValueError` above would be a 500.
Replace the return:

```python
    try:
        return update_transaction(
            db,
            transaction,
            data,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
```

- [ ] **Step 5 (R1): Pin that a legacy row stays unattributed**

Append to `backend/tests/test_transaction_stock.py`:

```python
def test_editing_a_pre_rollout_row_leaves_it_unattributed(
    client, db, test_products,
):
    """
    production_cycle_id IS NULL is the legacy marker the forecast's
    production series reads (see services/forecasting.py). An edit
    to a pre-rollout row must not claim it for a cycle, or its
    stored produced figure would vanish from the chart.
    """

    from app.services.transaction import update_transaction
    from app.schemas.transaction import SalesTransactionUpdate
    from app.database.models import SalesTransaction

    product = test_products[0]

    legacy = SalesTransaction(
        transaction_number="TRX-LEG001",
        product_id=product.id,
        production_cycle_id=None,
        transaction_date=datetime(2026, 8, 23),
        quantity=Decimal("1"),
        quantity_produced=Decimal("5"),
        unit_price=Decimal("100.00"),
        total_sales=Decimal("100.00"),
        production_cost=Decimal("0.00"),
        unit_profit=Decimal("0.00"),
        total_profit=Decimal("0.00"),
    )

    db.add(legacy)
    db.commit()
    db.refresh(legacy)

    try:
        updated = update_transaction(
            db,
            legacy,
            SalesTransactionUpdate(
                transaction_date=datetime(2026, 8, 24),
            ),
        )

        assert updated.production_cycle_id is None
        assert updated.quantity_produced == Decimal("5")

    finally:
        db.delete(legacy)
        db.commit()
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_transaction_stock.py -v
```

Expected: 15 passed.

- [ ] **Step 7: Run the whole backend suite**

```bash
cd backend && python -m pytest -q
```

Expected: green apart from the Task 0 baseline. `test_update_transaction_recalculates_totals`
(`tests/test_transactions.py:204`) must still pass — it exercises the non-zero-produced branch,
which is unchanged.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/transaction.py backend/app/routers/transactions.py \
        backend/tests/test_transaction_stock.py
git commit -m "feat: validate stock on transaction update; fix zero-produced division

Updates are now checked against available stock with the row's own
quantity added back so an edit never double-counts itself, the PATCH
handler turns ValueError into a 400 instead of a 500, and the per-unit
cost reconstruction no longer divides by a zero produced quantity.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 12: Frontend — inventory and opening-inventory API layers

**Requirements covered:** foundation for Tasks 13-16. No UI yet.

**Files:**
- Create: `frontend/src/pages/inventory/api/inventoryTypes.ts`
- Create: `frontend/src/pages/inventory/api/inventoryApi.ts`
- Create: `frontend/src/pages/inventory/api/inventoryAdapter.ts`
- Create: `frontend/src/pages/inventory/api/inventoryAdapter.test.ts`
- Create: `frontend/src/pages/inventory/types.ts`
- Create: `frontend/src/pages/opening-inventory/api/openingInventoryTypes.ts`
- Create: `frontend/src/pages/opening-inventory/api/openingInventoryApi.ts`

**Interfaces:**
- Consumes: `apiClient` from `frontend/src/api/client.ts`.
- Produces: `fetchInventory()`, `fetchOpeningInventorySets()`, `fetchOpeningInventoryStatus()`, `createOpeningInventorySet(data)`, `updateOpeningInventorySet(id, data)`, `reviewOpeningInventorySet(id)`, `toUiInventory(response)`, and the `ProductInventory` / `InventoryOverview` UI types.

- [ ] **Step 1: Write the failing adapter test**

Create `frontend/src/pages/inventory/api/inventoryAdapter.test.ts`:

```ts
import { describe, expect, it } from 'vitest'

import { toUiInventory } from './inventoryAdapter'

import type { InventoryOverviewResponse } from './inventoryTypes'

const response: InventoryOverviewResponse = {
  cycle_id: 3,
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

describe('toUiInventory', () => {
  it('parses every decimal string into a number', () => {
    const result = toUiInventory(response)

    expect(result.products[0]).toEqual({
      productId: 1,
      productName: 'Ordinary Table',
      openingQuantity: 4,
      totalProduced: 20,
      totalSold: 9,
      availableStock: 15,
      cycleProduced: 20,
      cycleSold: 9,
    })
  })

  it('carries the cycle window and the validation gate through', () => {
    const result = toUiInventory(response)

    expect(result.cycleId).toBe(3)
    expect(result.stockValidationEnabled).toBe(true)
  })

  it('survives a response with no production cycle', () => {
    const result = toUiInventory({
      ...response,
      cycle_id: null,
      cycle_start_date: null,
      cycle_end_date: null,
      stock_validation_enabled: false,
      products: [],
    })

    expect(result.cycleId).toBeNull()
    expect(result.stockValidationEnabled).toBe(false)
    expect(result.products).toEqual([])
  })
})
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd frontend && npx vitest run src/pages/inventory/api/inventoryAdapter.test.ts
```

Expected: `Failed to resolve import "./inventoryAdapter"`.

- [ ] **Step 3: Write the types**

Create `frontend/src/pages/inventory/api/inventoryTypes.ts`:

```ts
// Mirrors backend/app/schemas/inventory.py exactly. Every Decimal
// field arrives as a JSON string, never a bare number - the same
// convention as every other Decimal field in this backend.

export interface ProductInventoryResponse {
  product_id: number
  product_name: string
  opening_quantity: string
  total_produced: string
  total_sold: string
  available_stock: string
  cycle_produced: string
  cycle_sold: string
}

export interface InventoryOverviewResponse {
  cycle_id: number | null
  cycle_start_date: string | null
  cycle_end_date: string | null
  // False until an opening inventory set has been reviewed. While
  // false the backend does NOT enforce stock on sales, so the UI must
  // say so rather than implying the numbers are being enforced.
  stock_validation_enabled: boolean
  products: ProductInventoryResponse[]
}
```

Create `frontend/src/pages/inventory/types.ts`:

```ts
export interface ProductInventory {
  productId: number
  productName: string

  // Declared opening balance from the reviewed set; 0 when none was
  // declared for this product.
  openingQuantity: number

  // All-cycles totals.
  totalProduced: number
  totalSold: number

  // opening + totalProduced - totalSold. The real on-hand figure,
  // spanning every cycle - never reset by a new cycle.
  availableStock: number

  // CURRENT cycle only. These two reset when a new cycle starts;
  // availableStock does not.
  cycleProduced: number
  cycleSold: number
}

export interface InventoryOverview {
  cycleId: number | null
  cycleStartDate: string | null
  cycleEndDate: string | null
  stockValidationEnabled: boolean
  products: ProductInventory[]
}
```

- [ ] **Step 4: Write the adapter and api**

Create `frontend/src/pages/inventory/api/inventoryAdapter.ts`:

```ts
import type {
  InventoryOverviewResponse,
  ProductInventoryResponse,
} from './inventoryTypes'

import type {
  InventoryOverview,
  ProductInventory,
} from '../types'

// Same Decimal-as-JSON-string convention as every other adapter in
// this codebase (see transaction-history/api/transactionAdapter.ts) -
// duplicated locally rather than imported, matching the per-module
// convention.
function parseDecimal(value: string): number {
  const parsed = Number(value)

  return Number.isFinite(parsed) ? parsed : 0
}

function toUiProductInventory(
  row: ProductInventoryResponse,
): ProductInventory {
  return {
    productId: row.product_id,
    productName: row.product_name,
    openingQuantity: parseDecimal(row.opening_quantity),
    totalProduced: parseDecimal(row.total_produced),
    totalSold: parseDecimal(row.total_sold),
    availableStock: parseDecimal(row.available_stock),
    cycleProduced: parseDecimal(row.cycle_produced),
    cycleSold: parseDecimal(row.cycle_sold),
  }
}

export function toUiInventory(
  response: InventoryOverviewResponse,
): InventoryOverview {
  return {
    cycleId: response.cycle_id,
    cycleStartDate: response.cycle_start_date,
    cycleEndDate: response.cycle_end_date,
    stockValidationEnabled: response.stock_validation_enabled,
    products: response.products.map(toUiProductInventory),
  }
}
```

Create `frontend/src/pages/inventory/api/inventoryApi.ts`:

```ts
import apiClient from '../../../api/client'

import type { InventoryOverviewResponse } from './inventoryTypes'

export async function fetchInventory(): Promise<
  InventoryOverviewResponse
> {
  const response = await apiClient.get<InventoryOverviewResponse>(
    '/api/inventory',
  )

  return response.data
}
```

- [ ] **Step 5: Write the opening-inventory api layer**

Create `frontend/src/pages/opening-inventory/api/openingInventoryTypes.ts`:

```ts
// Mirrors backend/app/schemas/opening_inventory.py exactly.

export interface OpeningInventoryItemResponse {
  id: number
  product_id: number
  quantity: string
  notes: string | null
}

export interface OpeningInventorySetResponse {
  id: number
  set_number: string
  // "DRAFT" | "REVIEWED" | "SUPERSEDED" - see
  // app/services/opening_inventory.py for the only values written.
  status: string
  effective_date: string
  notes: string | null
  created_at: string
  reviewed_at: string | null
  created_by_username: string | null
  reviewed_by_username: string | null
  items: OpeningInventoryItemResponse[]
}

export interface OpeningInventoryStatusResponse {
  stock_validation_enabled: boolean
  reviewed_set: OpeningInventorySetResponse | null
  draft_set: OpeningInventorySetResponse | null
}

// Decimal inputs are sent as JS numbers, same convention as
// SalesTransactionCreateRequest.
export interface OpeningInventoryItemInput {
  product_id: number
  quantity: number
  notes?: string | null
}

export interface OpeningInventorySetCreateRequest {
  effective_date: string
  notes?: string | null
  items: OpeningInventoryItemInput[]
}

// items, when sent, REPLACES the whole list - the backend has no
// per-item merge, deliberately (see OpeningInventorySetUpdate).
export interface OpeningInventorySetUpdateRequest {
  effective_date?: string
  notes?: string | null
  items?: OpeningInventoryItemInput[]
}
```

Create `frontend/src/pages/opening-inventory/api/openingInventoryApi.ts`:

```ts
import apiClient from '../../../api/client'

import type {
  OpeningInventorySetCreateRequest,
  OpeningInventorySetResponse,
  OpeningInventorySetUpdateRequest,
  OpeningInventoryStatusResponse,
} from './openingInventoryTypes'

export async function fetchOpeningInventorySets(): Promise<
  OpeningInventorySetResponse[]
> {
  const response = await apiClient.get<
    OpeningInventorySetResponse[]
  >('/api/opening-inventory')

  return response.data
}

export async function fetchOpeningInventoryStatus(): Promise<
  OpeningInventoryStatusResponse
> {
  const response = await apiClient.get<
    OpeningInventoryStatusResponse
  >('/api/opening-inventory/active')

  return response.data
}

export async function createOpeningInventorySet(
  data: OpeningInventorySetCreateRequest,
): Promise<OpeningInventorySetResponse> {
  const response = await apiClient.post<
    OpeningInventorySetResponse
  >('/api/opening-inventory', data)

  return response.data
}

export async function updateOpeningInventorySet(
  setId: number,
  data: OpeningInventorySetUpdateRequest,
): Promise<OpeningInventorySetResponse> {
  const response = await apiClient.patch<
    OpeningInventorySetResponse
  >(`/api/opening-inventory/${setId}`, data)

  return response.data
}

// Flips DRAFT -> REVIEWED and supersedes any previously reviewed set.
// No request body - the router takes only set_id and reads the
// reviewer from the auth token.
export async function reviewOpeningInventorySet(
  setId: number,
): Promise<OpeningInventorySetResponse> {
  const response = await apiClient.post<
    OpeningInventorySetResponse
  >(`/api/opening-inventory/${setId}/review`)

  return response.data
}
```

- [ ] **Step 6: Run the test to verify it passes**

```bash
cd frontend && npx vitest run src/pages/inventory/api/inventoryAdapter.test.ts
```

Expected: 3 passed.

- [ ] **Step 7: Typecheck and commit**

```bash
cd frontend && npx tsc -b
git add frontend/src/pages/inventory frontend/src/pages/opening-inventory
git commit -m "feat(frontend): inventory and opening-inventory API layers

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 13: Frontend — Opening Inventory page (setup and review)

**Requirements covered:** "Require opening inventory setup to be completed and reviewed before enabling stock-based sales validation"; "Initial inventory: opening inventory. Do not start with zero."

**Files:**
- Create: `frontend/src/pages/opening-inventory/hooks/useOpeningInventory.ts`
- Create: `frontend/src/pages/opening-inventory/components/OpeningInventoryForm.tsx`
- Create: `frontend/src/pages/opening-inventory/components/ReviewConfirmModal.tsx`
- Create: `frontend/src/pages/opening-inventory/OpeningInventoryPage.tsx`
- Create: `frontend/src/pages/opening-inventory/OpeningInventoryPage.test.tsx`
- Modify: `frontend/src/app/router.tsx` (import + `/opening-inventory` route)
- Modify: `frontend/src/constants/navigation.ts` (nav entry)

**Interfaces:**
- Consumes: Task 12's opening-inventory api; `fetchProductSummaries` from `frontend/src/pages/transaction-history/api/transactionApi.ts`.
- Produces: `useOpeningInventory()` returning `{ sets, status, draftSet, reviewedSet, isStockValidationEnabled, products, isLoading, isError, saveDraft, reviewSet, isSaving, isReviewing }`.

- [ ] **Step 1: Write the failing page test**

Create `frontend/src/pages/opening-inventory/OpeningInventoryPage.test.tsx`. Follow the mocking
shape already used by `frontend/src/pages/resources-management/ResourcesPage.test.tsx` (read it
first for the exact `MantineProvider` + `QueryClientProvider` wrapper and `vi.mock` style used in
this repo), then assert:

```tsx
import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const mockReview = vi.fn().mockResolvedValue({})

vi.mock('./api/openingInventoryApi', () => ({
  fetchOpeningInventorySets: vi.fn().mockResolvedValue([]),
  fetchOpeningInventoryStatus: vi.fn().mockResolvedValue({
    stock_validation_enabled: false,
    reviewed_set: null,
    draft_set: null,
  }),
  createOpeningInventorySet: vi.fn().mockResolvedValue({ id: 1 }),
  updateOpeningInventorySet: vi.fn().mockResolvedValue({ id: 1 }),
  reviewOpeningInventorySet: mockReview,
}))

vi.mock(
  '../transaction-history/api/transactionApi',
  () => ({
    fetchProductSummaries: vi.fn().mockResolvedValue([
      { id: 1, name: 'Ordinary Table', selling_price: '2500.00' },
    ]),
  }),
)

describe('OpeningInventoryPage', () => {
  it('warns that stock validation is off until a set is reviewed', async () => {
    renderPage()

    expect(
      await screen.findByText(/not yet enforced/i),
    ).toBeInTheDocument()
  })

  it('lists every active product as a declarable row', async () => {
    renderPage()

    expect(
      await screen.findByText('Ordinary Table'),
    ).toBeInTheDocument()
  })

  it('requires confirmation before reviewing', async () => {
    renderPage({
      draft_set: {
        id: 1,
        set_number: 'OI-0001',
        status: 'DRAFT',
        effective_date: '2026-10-30T00:00:00',
        notes: null,
        created_at: '2026-10-30T00:00:00',
        reviewed_at: null,
        created_by_username: 'arvin',
        reviewed_by_username: null,
        items: [
          { id: 1, product_id: 1, quantity: '8.0000', notes: null },
        ],
      },
    })

    await userEvent.click(
      await screen.findByRole('button', { name: /mark as reviewed/i }),
    )

    expect(
      await screen.findByText(/cannot be edited afterwards/i),
    ).toBeInTheDocument()

    expect(mockReview).not.toHaveBeenCalled()

    await userEvent.click(
      screen.getByRole('button', { name: /^confirm review$/i }),
    )

    await waitFor(() => {
      expect(mockReview).toHaveBeenCalledWith(1)
    })
  })
})
```

Write the `renderPage` helper and the status-override plumbing to match the repo's existing test
helpers. The three assertions above are the contract this task must satisfy.

- [ ] **Step 2: Run it to verify it fails**

```bash
cd frontend && npx vitest run src/pages/opening-inventory/OpeningInventoryPage.test.tsx
```

Expected: cannot resolve `./OpeningInventoryPage`.

- [ ] **Step 3: Write the hook**

Create `frontend/src/pages/opening-inventory/hooks/useOpeningInventory.ts`:

```ts
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import {
  createOpeningInventorySet,
  fetchOpeningInventorySets,
  fetchOpeningInventoryStatus,
  reviewOpeningInventorySet,
  updateOpeningInventorySet,
} from '../api/openingInventoryApi'

import { fetchProductSummaries } from '../../transaction-history/api/transactionApi'

import type {
  OpeningInventorySetCreateRequest,
  OpeningInventorySetUpdateRequest,
} from '../api/openingInventoryTypes'

const OPENING_INVENTORY_KEY = ['opening-inventory']
const OPENING_INVENTORY_STATUS_KEY = [
  'opening-inventory',
  'status',
]

const useOpeningInventory = () => {
  const queryClient = useQueryClient()

  const setsQuery = useQuery({
    queryKey: OPENING_INVENTORY_KEY,
    queryFn: fetchOpeningInventorySets,
  })

  const statusQuery = useQuery({
    queryKey: OPENING_INVENTORY_STATUS_KEY,
    queryFn: fetchOpeningInventoryStatus,
  })

  const productsQuery = useQuery({
    queryKey: ['opening-inventory', 'products'],
    queryFn: fetchProductSummaries,
  })

  // Reviewing a set switches stock validation on, which changes what
  // EVERY stock-aware screen must show and enforce - so the inventory
  // overview and the transaction list both go stale here, not just
  // this page's own queries. Without this, Transaction History keeps
  // serving its cached unvalidated view for the full 5-minute global
  // staleTime (see app/providers.tsx, refetchOnWindowFocus off).
  const invalidateEverythingStockAware = () => {
    queryClient.invalidateQueries({
      queryKey: OPENING_INVENTORY_KEY,
    })
    queryClient.invalidateQueries({ queryKey: ['inventory'] })
    queryClient.invalidateQueries({ queryKey: ['transactions'] })
  }

  const createMutation = useMutation({
    mutationFn: (data: OpeningInventorySetCreateRequest) =>
      createOpeningInventorySet(data),
    onSuccess: invalidateEverythingStockAware,
  })

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number
      data: OpeningInventorySetUpdateRequest
    }) => updateOpeningInventorySet(id, data),
    onSuccess: invalidateEverythingStockAware,
  })

  const reviewMutation = useMutation({
    mutationFn: (id: number) => reviewOpeningInventorySet(id),
    onSuccess: invalidateEverythingStockAware,
  })

  return {
    sets: setsQuery.data ?? [],
    status: statusQuery.data ?? null,
    draftSet: statusQuery.data?.draft_set ?? null,
    reviewedSet: statusQuery.data?.reviewed_set ?? null,
    isStockValidationEnabled:
      statusQuery.data?.stock_validation_enabled ?? false,
    products: productsQuery.data ?? [],

    isLoading:
      setsQuery.isLoading ||
      statusQuery.isLoading ||
      productsQuery.isLoading,
    isError:
      setsQuery.isError ||
      statusQuery.isError ||
      productsQuery.isError,

    createDraft: createMutation.mutateAsync,
    updateDraft: updateMutation.mutateAsync,
    isSaving:
      createMutation.isPending || updateMutation.isPending,

    reviewSet: reviewMutation.mutateAsync,
    isReviewing: reviewMutation.isPending,
  }
}

export default useOpeningInventory
```

- [ ] **Step 4: Write the page and its two components**

`OpeningInventoryForm.tsx` renders one `NumberInput` per active product (`min={0}`, prefilled from
the draft set's items, `0` when absent) plus a date input for `effective_date` and a notes
`Textarea`, and calls `onSave(items)` with the full replacement list.

`ReviewConfirmModal.tsx` mirrors `production-allocation/components/ApplyConfirmModal.tsx`
exactly in structure (same `Alert color="orange"`, same `getApiErrorMessage` handling, same
`isSubmitting` guard), with this copy:

```tsx
      <Text mb="md">
        Mark this opening inventory as reviewed?
      </Text>

      <Alert
        color="orange"
        variant="light"
        icon={<AlertTriangle size={18} />}
        mb="md"
      >
        These balances become the authoritative starting point for every
        stock figure, and stock-based validation of sales switches on.
        A reviewed set cannot be edited afterwards — correcting it means
        creating a new set.
      </Alert>
```

and a confirm button labelled exactly `Confirm review`.

`OpeningInventoryPage.tsx` composes: a `PageHeader`, a status banner, the form (when a draft exists
or none exists yet), a `Mark as reviewed` button (disabled unless a draft with at least one item
exists), the review modal, and a history table of past sets (`set_number`, `status`,
`effective_date`, `reviewed_at`, `reviewed_by_username`).

The banner copy, keyed off `isStockValidationEnabled`:

```tsx
{isStockValidationEnabled ? (
  <Alert color="green" variant="light" icon={<ShieldCheck size={18} />}>
    Stock-based validation is active. Sales are checked against
    available stock, and {reviewedSet?.set_number} is the opening
    balance every stock figure starts from.
  </Alert>
) : (
  <Alert color="orange" variant="light" icon={<AlertTriangle size={18} />}>
    Available stock is not yet enforced. Declare the units you
    physically hold for each product and mark the set as reviewed —
    until then, sales are recorded without being checked against
    stock.
  </Alert>
)}
```

The `/not yet enforced/i` and `/cannot be edited afterwards/i` strings are asserted by Step 1 —
keep them verbatim.

- [ ] **Step 5: Register the route and nav entry**

In `frontend/src/app/router.tsx`, add the import alongside the others:

```tsx
import OpeningInventoryPage from '../pages/opening-inventory/OpeningInventoryPage'
```

and the route inside the `AppLayout` block, after `/products`:

```tsx
            <Route
              path="/opening-inventory"
              element={<OpeningInventoryPage />}
            />
```

In `frontend/src/constants/navigation.ts`, add `ClipboardCheck` to the `lucide-react` import and
this entry after `Products`:

```ts
  {
    label: 'Opening Stock',
    path: '/opening-inventory',
    icon: ClipboardCheck,
  },
```

- [ ] **Step 6: Run the test to verify it passes**

```bash
cd frontend && npx vitest run src/pages/opening-inventory
```

Expected: 3 passed.

- [ ] **Step 7: Typecheck, lint, commit**

```bash
cd frontend && npx tsc -b && npx eslint src/pages/opening-inventory
git add frontend/src/pages/opening-inventory frontend/src/app/router.tsx \
        frontend/src/constants/navigation.ts
git commit -m "feat(frontend): Opening Stock page with an explicit review step

Declaring balances is not enough - reviewing is what switches
stock-based sales validation on, and the page says so in both states.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 14: Frontend — Inventory Overview page

**Requirements covered:** "IMPORTANT DISTINCTION: Please investigate how to maintain these separately: Produced quantity for the current 7-day cycle / Sold quantity for the current 7-day cycle / Actual available inventory across all cycles." The page's job is to make those three visibly, labelled-ly distinct.

**Files:**
- Create: `frontend/src/pages/inventory/hooks/useInventory.ts`
- Create: `frontend/src/pages/inventory/components/InventoryTable.tsx`
- Create: `frontend/src/pages/inventory/components/InventorySummaryCards.tsx`
- Create: `frontend/src/pages/inventory/InventoryPage.tsx`
- Create: `frontend/src/pages/inventory/InventoryPage.test.tsx`
- Modify: `frontend/src/app/router.tsx`, `frontend/src/constants/navigation.ts`

**Interfaces:**
- Consumes: `fetchInventory`, `toUiInventory` (Task 12).
- Produces: `useInventory()` returning `{ inventory, products, cycleId, cycleStartDate, cycleEndDate, isStockValidationEnabled, isLoading, isError }`, under query key `['inventory']` — the key Tasks 13, 15 and 16 invalidate.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/pages/inventory/InventoryPage.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('./api/inventoryApi', () => ({
  fetchInventory: vi.fn().mockResolvedValue({
    cycle_id: 3,
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
  }),
}))

describe('InventoryPage', () => {
  it('shows cycle produced, cycle sold and available stock as separate columns', async () => {
    renderPage()

    expect(
      await screen.findByText('Ordinary Table'),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('columnheader', { name: /produced this cycle/i }),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('columnheader', { name: /sold this cycle/i }),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('columnheader', { name: /available stock/i }),
    ).toBeInTheDocument()
  })

  it('labels available stock as spanning all cycles', async () => {
    renderPage()

    expect(
      await screen.findByText(/across all cycles/i),
    ).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd frontend && npx vitest run src/pages/inventory/InventoryPage.test.tsx
```

Expected: cannot resolve `./InventoryPage`.

- [ ] **Step 3: Write the hook**

Create `frontend/src/pages/inventory/hooks/useInventory.ts`:

```ts
import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import { fetchInventory } from '../api/inventoryApi'
import { toUiInventory } from '../api/inventoryAdapter'

// The canonical inventory query key. Tasks that change stock -
// applying production, saving/reviewing opening inventory, and every
// transaction mutation - all invalidate exactly this key, so they do
// not need to know anything else about this module.
export const INVENTORY_QUERY_KEY = ['inventory']

const useInventory = () => {
  const inventoryQuery = useQuery({
    queryKey: INVENTORY_QUERY_KEY,
    queryFn: fetchInventory,
  })

  const inventory = useMemo(
    () =>
      inventoryQuery.data
        ? toUiInventory(inventoryQuery.data)
        : null,
    [inventoryQuery.data],
  )

  return {
    inventory,
    products: inventory?.products ?? [],
    cycleId: inventory?.cycleId ?? null,
    cycleStartDate: inventory?.cycleStartDate ?? null,
    cycleEndDate: inventory?.cycleEndDate ?? null,
    isStockValidationEnabled:
      inventory?.stockValidationEnabled ?? false,

    isLoading: inventoryQuery.isLoading,
    isError: inventoryQuery.isError,
  }
}

export default useInventory
```

- [ ] **Step 4: Write the table, cards, and page**

`InventoryTable.tsx` renders columns in exactly this order and with exactly these headers (the test
asserts three of them):

| Header | Field |
|---|---|
| `Product` | `productName` |
| `Opening` | `openingQuantity` |
| `Produced This Cycle` | `cycleProduced` |
| `Sold This Cycle` | `cycleSold` |
| `Available Stock` | `availableStock` |

Build it on the existing `frontend/src/components/tables/AppTable.tsx` the way
`resource-utilization-report/components/UtilizationTable.tsx` does. Render `Available Stock` with
`fw={600}` and a `Text size="xs" c="dimmed"` caption reading `across all cycles` directly under the
header group (the string the second test asserts).

`InventorySummaryCards.tsx` shows three `StatCard`s (reuse
`frontend/src/components/cards/StatCard.tsx`): total units produced this cycle, total units sold
this cycle, total units available. Each card's subtitle must name its scope — `this cycle`,
`this cycle`, `all cycles` — because the whole point of the page is that the three are different
quantities.

`InventoryPage.tsx` composes `PageHeader` (title `Inventory`, subtitle naming the current cycle
window from `cycleStartDate`/`cycleEndDate`), the summary cards, the table, `LoadingView` /
`ErrorView` / `NoDataView` from `frontend/src/components/feedback/`, and — when
`isStockValidationEnabled` is false — the same orange "not yet enforced" `Alert` as Task 13, with a
`Link` to `/opening-inventory`.

- [ ] **Step 5: Register the route and nav entry**

`router.tsx`: `import InventoryPage from '../pages/inventory/InventoryPage'` and

```tsx
            <Route
              path="/inventory"
              element={<InventoryPage />}
            />
```

`navigation.ts`: add `Warehouse` to the `lucide-react` import and

```ts
  {
    label: 'Inventory',
    path: '/inventory',
    icon: Warehouse,
  },
```

placed directly after the `Opening Stock` entry.

- [ ] **Step 6: Run the test, typecheck, lint, commit**

```bash
cd frontend && npx vitest run src/pages/inventory && npx tsc -b && npx eslint src/pages/inventory
git add frontend/src/pages/inventory frontend/src/app/router.tsx \
        frontend/src/constants/navigation.ts
git commit -m "feat(frontend): Inventory page separating cycle totals from stock

Produced this cycle, sold this cycle, and available stock across all
cycles are three different quantities, so the page labels them as
three different columns rather than letting them read as one.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 15: Frontend — Add Transaction modal: read-only produced quantity and a stock cap

**Requirements covered:** "Quantity Produced: read-only"; "Do not require users to manually enter or synchronize the produced quantity"; "Reject sales exceeding available stock"; "Do not use available stock as newly produced quantity."

**Files:**
- Create: `frontend/src/pages/transaction-history/api/inventoryApi.ts` (local slice)
- Modify: `frontend/src/pages/transaction-history/hooks/useTransactions.ts`
- Modify: `frontend/src/pages/transaction-history/components/AddTransactionModal.tsx`
- Modify: `frontend/src/pages/transaction-history/api/transactionTypes.ts`
- Modify: `frontend/src/pages/transaction-history/components/AddTransactionModal.test.tsx`
- Modify: `frontend/src/pages/transaction-history/TransactionHistoryPage.tsx` (pass the new props)

**Interfaces:**
- Consumes: `GET /api/inventory`.
- Produces: `fetchInventorySlice()`; `useTransactions` additionally returns `{ stockByProductId, producedByProductId, isStockValidationEnabled }`; `AddTransactionModal` gains props `stockByProductId: Record<number, number>`, `producedByProductId: Record<number, number>`, `isStockValidationEnabled: boolean`.

- [ ] **Step 1: Write the failing tests**

Modify `frontend/src/pages/transaction-history/components/AddTransactionModal.test.tsx` — keep the
four existing tests (adjusting their props for the three new required ones) and add:

```tsx
  it('shows Quantity Produced as read-only and filled from applied production', async () => {
    renderModal({
      producedByProductId: { 1: 10 },
      stockByProductId: { 1: 15 },
      isStockValidationEnabled: true,
    })

    await userEvent.click(screen.getByLabelText(/furniture product/i))
    await userEvent.click(
      await screen.findByRole('option', { name: 'Ordinary Table' }),
    )

    const producedInput = screen.getByLabelText(
      /quantity produced/i,
    ) as HTMLInputElement

    expect(producedInput).toHaveAttribute('readonly')
    expect(producedInput.value).toBe('10')
  })

  it('shows available stock for the selected product', async () => {
    renderModal({
      producedByProductId: { 1: 10 },
      stockByProductId: { 1: 15 },
      isStockValidationEnabled: true,
    })

    await userEvent.click(screen.getByLabelText(/furniture product/i))
    await userEvent.click(
      await screen.findByRole('option', { name: 'Ordinary Table' }),
    )

    expect(
      await screen.findByText(/15 units available/i),
    ).toBeInTheDocument()
  })

  it('blocks a quantity sold above available stock', async () => {
    const onSave = vi.fn()

    renderModal({
      onSave,
      producedByProductId: { 1: 10 },
      stockByProductId: { 1: 15 },
      isStockValidationEnabled: true,
    })

    await userEvent.click(screen.getByLabelText(/furniture product/i))
    await userEvent.click(
      await screen.findByRole('option', { name: 'Ordinary Table' }),
    )

    await userEvent.clear(screen.getByLabelText(/quantity sold/i))
    await userEvent.type(
      screen.getByLabelText(/quantity sold/i),
      '16',
    )

    expect(
      await screen.findByText(/only 15 units are available/i),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: /^save$/i }),
    ).toBeDisabled()

    expect(onSave).not.toHaveBeenCalled()
  })

  it('does not cap the quantity sold while validation is off', async () => {
    renderModal({
      producedByProductId: {},
      stockByProductId: {},
      isStockValidationEnabled: false,
    })

    await userEvent.click(screen.getByLabelText(/furniture product/i))
    await userEvent.click(
      await screen.findByRole('option', { name: 'Ordinary Table' }),
    )

    await userEvent.clear(screen.getByLabelText(/quantity sold/i))
    await userEvent.type(screen.getByLabelText(/quantity sold/i), '99')

    expect(
      screen.queryByText(/units are available/i),
    ).not.toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: /^save$/i }),
    ).toBeEnabled()
  })

  it('omits quantity_produced from the create payload', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined)

    renderModal({
      onSave,
      producedByProductId: { 1: 10 },
      stockByProductId: { 1: 15 },
      isStockValidationEnabled: true,
    })

    await userEvent.click(screen.getByLabelText(/furniture product/i))
    await userEvent.click(
      await screen.findByRole('option', { name: 'Ordinary Table' }),
    )

    await userEvent.clear(screen.getByLabelText(/quantity sold/i))
    await userEvent.type(screen.getByLabelText(/quantity sold/i), '3')

    await userEvent.click(
      screen.getByRole('button', { name: /^save$/i }),
    )

    await waitFor(() => {
      expect(onSave).toHaveBeenCalled()
    })

    expect(
      onSave.mock.calls[0][0],
    ).not.toHaveProperty('quantity_produced')
  })
```

- [ ] **Step 2: Run them to verify they fail**

```bash
cd frontend && npx vitest run src/pages/transaction-history/components/AddTransactionModal.test.tsx
```

Expected: the produced input is editable and starts at 0, no stock text renders, and the payload
still carries `quantity_produced`.

- [ ] **Step 3: Add the local inventory slice**

Create `frontend/src/pages/transaction-history/api/inventoryApi.ts`:

```ts
import apiClient from '../../../api/client'

// Minimal local slice of GET /api/inventory - only what this page
// needs to show available stock and the auto-filled produced figure.
// Same local-copy convention already used by this page's
// ProductSummary and by production-allocation/api/productionTypes.ts.
export interface InventorySliceRow {
  product_id: number
  available_stock: string
  cycle_produced: string
}

export interface InventorySliceResponse {
  stock_validation_enabled: boolean
  products: InventorySliceRow[]
}

export async function fetchInventorySlice(): Promise<
  InventorySliceResponse
> {
  const response = await apiClient.get<InventorySliceResponse>(
    '/api/inventory',
  )

  return response.data
}
```

- [ ] **Step 4: Extend `useTransactions`**

In `frontend/src/pages/transaction-history/hooks/useTransactions.ts`, add the import and query, and
extend every mutation's `onSuccess` to invalidate `['inventory']`:

```ts
import { fetchInventorySlice } from '../api/inventoryApi'

const INVENTORY_QUERY_KEY = ['inventory']
```

```ts
  const inventoryQuery = useQuery({
    queryKey: INVENTORY_QUERY_KEY,
    queryFn: fetchInventorySlice,
  })
```

```ts
  // Every transaction mutation changes available stock (the sold half
  // of the derivation), so the inventory figures this page shows - and
  // the Inventory page's own ['inventory'] query - go stale on each
  // one. Shares the key with inventory/hooks/useInventory.ts on
  // purpose: one key, every writer invalidates it.
  const invalidateInventory = () =>
    queryClient.invalidateQueries({
      queryKey: INVENTORY_QUERY_KEY,
    })
```

Call `invalidateInventory()` alongside `invalidateTransactions()` in all three mutations' `onSuccess`,
and add to the returned object:

```ts
    stockByProductId: Object.fromEntries(
      (inventoryQuery.data?.products ?? []).map((row) => [
        row.product_id,
        Number(row.available_stock),
      ]),
    ),

    // cycle_produced, NOT available_stock. The produced figure must
    // never be available stock: that spans every cycle and includes
    // opening inventory, so showing it as "newly produced" would
    // overstate what this cycle produced. The server
    // computes the authoritative value anyway (a per-cycle drawdown);
    // this is a display-only preview of it.
    producedByProductId: Object.fromEntries(
      (inventoryQuery.data?.products ?? []).map((row) => [
        row.product_id,
        Number(row.cycle_produced),
      ]),
    ),

    isStockValidationEnabled:
      inventoryQuery.data?.stock_validation_enabled ?? false,
```

- [ ] **Step 5: Rework `AddTransactionModal`**

Changes to `frontend/src/pages/transaction-history/components/AddTransactionModal.tsx`:

1. Add the three props to `AddTransactionModalProps`.
2. Replace the `quantityProduced` state's manual control. Derive it instead:

```tsx
  // Server-computed on create (see app/services/transaction.py::
  // create_transaction, which auto-fills it from the ledger as a
  // per-cycle drawdown and ignores anything sent here). Shown
  // read-only so the user can see what will be recorded without being
  // able to desynchronise it. In edit mode the stored value is shown
  // as-is: update_transaction deliberately does not re-derive it,
  // because re-deriving would reshuffle the drawdown across every row
  // in the cycle and rewrite settled history.
  const displayedQuantityProduced = isEditMode
    ? (transaction?.quantityProduced ?? 0)
    : productId !== null
      ? (producedByProductId[productId] ?? 0)
      : 0

  const availableStock =
    productId !== null
      ? (stockByProductId[productId] ?? 0)
      : 0

  const exceedsStock =
    isStockValidationEnabled &&
    !isEditMode &&
    productId !== null &&
    quantitySold > availableStock
```

3. Make the `Quantity Produced` input read-only and derived:

```tsx
          <NumberInput
            radius="md"
            label="Quantity Produced"
            value={displayedQuantityProduced}
            readOnly
            description="Filled automatically from applied production"
          />
```

4. Add the stock caption and the over-stock error under `Quantity Sold`:

```tsx
          <NumberInput
            radius="md"
            label="Quantity Sold"
            value={quantitySold}
            onChange={(value) => setQuantitySold(Number(value))}
            min={0}
            max={
              isStockValidationEnabled && !isEditMode
                ? availableStock
                : undefined
            }
            error={
              exceedsStock
                ? `Only ${availableStock} units are available`
                : undefined
            }
            description={
              isStockValidationEnabled && productId !== null
                ? `${availableStock} units available`
                : undefined
            }
          />
```

5. Extend the `isValid` guard so Save is disabled on an oversell, and drop the
   `quantityProduced > 0` requirement (it is no longer user-controlled, and `0` is legitimate):

```tsx
  const isValid =
    productId !== null &&
    date.trim() !== '' &&
    quantitySold > 0 &&
    unitPrice > 0 &&
    !exceedsStock
```

6. Remove `quantity_produced` from **both** payloads in `handleSave`. The create payload becomes:

```tsx
        // quantity_produced is omitted entirely: the server computes
        // it from the production ledger. production_cost is still
        // required by the create contract and this form does not
        // collect one, so new transactions are recorded at 0.
        await onSave({
          product_id: productId as number,
          transaction_date: `${date}T00:00:00`,
          quantity: quantitySold,
          unit_price: unitPrice,
          production_cost: 0,
        })
```

and the edit payload drops `quantity_produced` for the same reason the comment above it already
gives for `production_cost`.

7. Delete the now-unused `quantityProduced`/`setQuantityProduced` state and its two `useEffect`
   assignments.

- [ ] **Step 6: Make `quantity_produced` optional in the request types**

In `frontend/src/pages/transaction-history/api/transactionTypes.ts`:

```ts
// quantity_produced is SERVER-COMPUTED and deliberately absent here:
// app/services/transaction.py::create_transaction fills it from the
// production ledger and ignores any value sent. The backend schema
// still accepts it for older clients, but this client must not send
// one.
export interface SalesTransactionCreateRequest {
  product_id: number
  transaction_date: string
  quantity: number
  unit_price: number
  production_cost: number
}
```

and in `SalesTransactionUpdateRequest`, keep `quantity_produced?: number` with a comment noting the
UI never sends it (the backend still honours it for a deliberate correction).

- [ ] **Step 7: Pass the props through the page**

In `frontend/src/pages/transaction-history/TransactionHistoryPage.tsx`, destructure the three new
values from `useTransactions()` and forward them to `<AddTransactionModal ... />`.

- [ ] **Step 8: Run the tests, typecheck, lint, commit**

```bash
cd frontend && npx vitest run src/pages/transaction-history && npx tsc -b \
  && npx eslint src/pages/transaction-history
git add frontend/src/pages/transaction-history
git commit -m "feat(frontend): read-only produced quantity and a stock cap on sales

Quantity Produced is filled from applied production and no longer
editable or sent; Quantity Sold is capped at available stock whenever
opening inventory has been reviewed.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 16: Frontend — Production Allocation: additive apply copy and already-applied state

**Requirements covered:** "Every successfully applied allocation should add its production quantity. It must not overwrite previously applied production within the same cycle" (the UI must stop saying the opposite); "Reject duplicate applications of the same optimization run" (surface it before the user clicks).

**The current copy is now actively wrong.** `ApplyConfirmModal.tsx` says *"This will replace the
current committed allocation for this production cycle with the latest optimal plan."* Production is
now additive, so this has to change.

**Files:**
- Modify: `frontend/src/pages/production-allocation/api/productionApi.ts` (fetch applications)
- Modify: `frontend/src/pages/production-allocation/api/productionTypes.ts`
- Modify: `frontend/src/pages/production-allocation/hooks/useProductionAllocation.ts`
- Modify: `frontend/src/pages/production-allocation/components/ApplyConfirmModal.tsx`
- Modify: `frontend/src/pages/production-allocation/ProductionAllocationPage.tsx`
- Modify: `frontend/src/pages/production-allocation/hooks/useProductionAllocation.test.tsx`
- Modify: `frontend/src/pages/production-allocation/ProductionAllocationPage.test.tsx`

**Interfaces:**
- Consumes: `GET /api/production-cycles/{cycle_id}/applications`.
- Produces: `fetchProductionApplications(cycleId)`; `useProductionAllocation` additionally returns `{ isCurrentPlanApplied, appliedCount, cycleProducedTotal }`; `canApply` now also requires `!isCurrentPlanApplied`.

- [ ] **Step 1: Write the failing tests**

Append to `frontend/src/pages/production-allocation/hooks/useProductionAllocation.test.tsx`:

```tsx
  it('invalidates the inventory query after a successful apply', async () => {
    const { queryClient, result } = renderHookWithMocks()

    const spy = vi.spyOn(queryClient, 'invalidateQueries')

    await act(async () => {
      await result.current.applyToProduction()
    })

    expect(spy).toHaveBeenCalledWith({ queryKey: ['inventory'] })
  })

  it('reports the current plan as already applied and blocks Apply', async () => {
    const { result } = renderHookWithMocks({
      applications: [
        {
          id: 1,
          application_number: 'PA-0001',
          production_cycle_id: 1,
          // Must match the run id findLatestOptimalRun resolves from
          // the mocked history.
          optimization_run_id: 7,
          applied_at: '2026-10-30T09:00:00',
          product_items: [
            { product_id: 1, quantity_produced: '10.0000' },
          ],
          resource_items: [],
        },
      ],
    })

    await waitFor(() => {
      expect(result.current.isCurrentPlanApplied).toBe(true)
    })

    expect(result.current.canApply).toBe(false)
  })
```

Append to `ProductionAllocationPage.test.tsx`:

```tsx
  it('tells the user Apply will add to this cycle, not replace it', async () => {
    renderPage()

    await userEvent.click(
      await screen.findByRole('button', { name: /apply to production/i }),
    )

    expect(
      await screen.findByText(/add .* to this cycle/i),
    ).toBeInTheDocument()

    expect(
      screen.queryByText(/replace the current committed allocation/i),
    ).not.toBeInTheDocument()
  })

  it('explains why Apply is unavailable for an already-applied plan', async () => {
    renderPage({ currentPlanApplied: true })

    expect(
      await screen.findByText(/already been applied/i),
    ).toBeInTheDocument()
  })
```

Extend the existing `renderHookWithMocks`/`renderPage` helpers with the new `applications` and
`currentPlanApplied` options, matching how they already stub `fetchOptimizationHistory`.

- [ ] **Step 2: Run them to verify they fail**

```bash
cd frontend && npx vitest run src/pages/production-allocation
```

Expected: `isCurrentPlanApplied` is undefined, `['inventory']` is never invalidated, and the modal
still shows the "replace" copy.

- [ ] **Step 3: Add the API call and type**

In `productionTypes.ts`:

```ts
// Mirrors backend/app/schemas/production_application.py. One entry per
// Apply event - the append-only ledger, NOT the current committed
// allocation (that is ProductionAllocationResponse above).
export interface ProductionApplicationItemResponse {
  product_id: number
  quantity_produced: string
}

export interface ProductionApplicationResourceItemResponse {
  resource_id: number | null
  resource_name: string
  unit: string
  consumed_quantity: string
}

export interface ProductionApplicationResponse {
  id: number
  application_number: string
  production_cycle_id: number
  optimization_run_id: number
  applied_at: string
  product_items: ProductionApplicationItemResponse[]
  resource_items: ProductionApplicationResourceItemResponse[]
}
```

In `productionApi.ts`:

```ts
// The append-only production ledger for a cycle. Distinct from
// fetchProductionAllocations above: that returns the CURRENT committed
// plan (one row per product, replaced on each apply), this returns
// every apply event that ever happened in the cycle.
export async function fetchProductionApplications(
  cycleId: number,
): Promise<ProductionApplicationResponse[]> {
  const response = await apiClient.get<
    ProductionApplicationResponse[]
  >(`/api/production-cycles/${cycleId}/applications`)

  return response.data
}
```

- [ ] **Step 4: Extend the hook**

In `useProductionAllocation.ts`, add the query and the derived flags:

```ts
  const applicationsQueryKey = [
    'production-applications',
    latestCycleId,
  ]

  const applicationsQuery = useQuery({
    queryKey: applicationsQueryKey,
    queryFn: () => fetchProductionApplications(latestCycleId!),
    enabled: latestCycleId !== null,
  })

  // The backend rejects applying a run that already has a ledger row
  // (apply_optimization's has_application_for_run guard). Mirroring
  // that check here is purely so the user is told BEFORE clicking,
  // rather than by a 400 afterwards - the server's guard and the
  // uq_production_application_run constraint remain the real
  // enforcement.
  const isCurrentPlanApplied = useMemo(() => {
    if (!latestOptimalRun) {
      return false
    }

    return (applicationsQuery.data ?? []).some(
      (application) =>
        application.optimization_run_id === latestOptimalRun.id,
    )
  }, [applicationsQuery.data, latestOptimalRun])

  const cycleProducedTotal = useMemo(
    () =>
      (applicationsQuery.data ?? []).reduce(
        (runningTotal, application) =>
          runningTotal +
          application.product_items.reduce(
            (itemTotal, item) =>
              itemTotal + Number(item.quantity_produced),
            0,
          ),
        0,
      ),
    [applicationsQuery.data],
  )
```

Place `isCurrentPlanApplied` **after** the existing `latestOptimalRun` memo (it depends on it).
Change the returned `canApply` and add the new values:

```ts
    canApply: latestOptimalRun !== null && !isCurrentPlanApplied,
    isCurrentPlanApplied,
    appliedCount: (applicationsQuery.data ?? []).length,
    cycleProducedTotal,
```

In `applyMutation.onSuccess`, add:

```ts
      // The ledger gained a row, so this cycle's application list and
      // every derived stock figure go stale. ['inventory'] is shared
      // with inventory/hooks/useInventory.ts and
      // transaction-history/hooks/useTransactions.ts - one key, every
      // writer invalidates it.
      queryClient.invalidateQueries({
        queryKey: applicationsQueryKey,
      })

      queryClient.invalidateQueries({ queryKey: ['inventory'] })
```

Also replace the stale comment block above `allocationsQuery` that reads *"Only ever written by
POST /optimize/apply or direct manual CRUD... so this is deliberately NOT invalidated by the
optimize mutation"* — the first clause is still true, but add a sentence noting that production
history now lives in `applicationsQuery`, not here.

- [ ] **Step 5: Rewrite the modal copy**

In `ApplyConfirmModal.tsx`, add a `cycleProducedTotal: number` and `plannedTotal: number` prop and
replace the body text and alert:

```tsx
      <Text mb="md">
        Apply this production plan?
      </Text>

      <Alert
        color="blue"
        variant="light"
        icon={<AlertTriangle size={18} />}
        mb="md"
      >
        This will add {plannedTotal} units to this cycle
        {cycleProducedTotal > 0
          ? `, on top of the ${cycleProducedTotal} units already applied`
          : ''}
        , and consume the matching resource capacity. Previously
        applied production is never overwritten.
      </Alert>
```

The `/add .* to this cycle/i` string is asserted by Step 1's page test — keep the wording.

- [ ] **Step 6: Surface the already-applied state on the page**

In `ProductionAllocationPage.tsx`, destructure `isCurrentPlanApplied`, `appliedCount` and
`cycleProducedTotal`, pass the latter two into the modal, and render — next to the Apply button,
where the existing `needsReoptimization` banner renders — this alert when
`isCurrentPlanApplied` is true:

```tsx
        {isCurrentPlanApplied && (
          <Alert
            color="gray"
            variant="light"
            icon={<Info size={18} />}
          >
            This production plan has already been applied
            {cycleProducedTotal > 0
              ? ` (${cycleProducedTotal} units produced in this cycle so far)`
              : ''}
            . Generate a new plan to produce more — re-applying the
            same plan would double-count its units.
          </Alert>
        )}
```

Import `Info` from `lucide-react`. The existing `applyDisabled` already folds in `canApply`, so no
further change is needed there.

- [ ] **Step 7: Run the tests, typecheck, lint, commit**

```bash
cd frontend && npx vitest run src/pages/production-allocation && npx tsc -b \
  && npx eslint src/pages/production-allocation
git add frontend/src/pages/production-allocation
git commit -m "feat(frontend): Apply adds to the cycle instead of replacing it

Apply copy now says it adds units on top of what the cycle already
produced, an already-applied plan disables Apply with an explanation,
and a successful apply invalidates the shared inventory query.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 17: Playwright end-to-end coverage

**Requirements covered:** the user's explicit request for a Playwright test plan. **Playwright is not
installed in this repo today** (`frontend/package.json` has vitest/RTL only) — this task introduces
it.

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/fixtures/apiStubs.ts`
- Create: `frontend/e2e/opening-inventory.spec.ts`
- Create: `frontend/e2e/production-cycle.spec.ts`
- Modify: `frontend/package.json` (devDependency + `test:e2e` script)
- Modify: `.gitignore` (add `frontend/test-results/`, `frontend/playwright-report/`)

**Interfaces:**
- Consumes: the running frontend dev server plus route-level API stubbing (`page.route`). These specs
  do **not** hit the real backend, so no database is involved — which is what keeps them safe to run
  alongside the Global Constraints.

- [ ] **Step 1: Install Playwright**

```bash
cd frontend && npm install --save-dev @playwright/test && npx playwright install chromium
```

Add to `package.json` scripts:

```json
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui"
```

- [ ] **Step 2: Add the config**

Create `frontend/playwright.config.ts`:

```ts
import { defineConfig, devices } from '@playwright/test'

// The e2e suite stubs every /api/** call at the network layer (see
// e2e/fixtures/apiStubs.ts) and never talks to a real backend, so it
// touches no database. That is deliberate: these specs assert the UI's
// own behaviour - what it shows, blocks and sends - which is exactly
// the layer vitest/RTL cannot cover end to end.
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: 0,
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: true,
    timeout: 120_000,
  },
})
```

- [ ] **Step 3: Add the stub fixture**

Create `frontend/e2e/fixtures/apiStubs.ts` exporting `installApiStubs(page, overrides)`, which
`page.route('**/api/**')`s and fulfils:

- `POST /api/auth/login` and `GET /api/auth/me` → a logged-in user (so `ProtectedRoute` passes;
  check `frontend/src/auth/AuthContext.tsx` for the exact shape and seed `localStorage` via
  `page.addInitScript` using the key from `frontend/src/api/tokenStorage.ts`)
- `GET /api/products` → one product, `Ordinary Table`
- `GET /api/production-cycles/latest` → a cycle covering the test dates
- `GET /api/inventory` → the overview, driven by `overrides.inventory`
- `GET /api/opening-inventory/active` → driven by `overrides.openingStatus`
- `GET /api/transactions` → driven by `overrides.transactions`
- `GET /api/optimization/history`, `GET /api/production-cycles/:id/allocations`,
  `GET /api/production-cycles/:id/applications`, `GET /api/production-cycles/:id/feasibility`
- `POST` routes → record the request body on a shared array the specs assert against

- [ ] **Step 4: Write `opening-inventory.spec.ts`**

```ts
import { expect, test } from '@playwright/test'

import { installApiStubs } from './fixtures/apiStubs'

test('stock validation is advertised as off until a set is reviewed', async ({ page }) => {
  await installApiStubs(page, {
    openingStatus: {
      stock_validation_enabled: false,
      reviewed_set: null,
      draft_set: null,
    },
  })

  await page.goto('/opening-inventory')

  await expect(page.getByText(/not yet enforced/i)).toBeVisible()
})

test('reviewing a draft requires confirmation and then reports validation active', async ({ page }) => {
  const requests = await installApiStubs(page, {
    openingStatus: {
      stock_validation_enabled: false,
      reviewed_set: null,
      draft_set: {
        id: 1,
        set_number: 'OI-0001',
        status: 'DRAFT',
        effective_date: '2026-10-30T00:00:00',
        notes: null,
        created_at: '2026-10-30T00:00:00',
        reviewed_at: null,
        created_by_username: 'arvin',
        reviewed_by_username: null,
        items: [
          { id: 1, product_id: 1, quantity: '8.0000', notes: null },
        ],
      },
    },
  })

  await page.goto('/opening-inventory')

  await page
    .getByRole('button', { name: /mark as reviewed/i })
    .click()

  await expect(
    page.getByText(/cannot be edited afterwards/i),
  ).toBeVisible()

  await page
    .getByRole('button', { name: /^confirm review$/i })
    .click()

  await expect
    .poll(() => requests.reviewCalls.length)
    .toBe(1)
})
```

- [ ] **Step 5: Write `production-cycle.spec.ts`**

Four scenarios, each asserting UI behaviour the unit tests cannot reach end to end:

1. **Apply copy is additive.** `/production` → open the Apply modal → expect text matching
   `/add \d+ units to this cycle/i` and **no** text matching `/replace the current committed/i`.
2. **Already-applied plan blocks Apply.** Stub `/applications` to contain the latest optimal run's
   id → expect `/already been applied/i` visible and the `Apply to Production` button disabled.
3. **Quantity Produced is read-only and auto-filled.** `/history` → Add Transaction → select
   `Ordinary Table` → expect the `Quantity Produced` input to have the `readonly` attribute and the
   value from `cycle_produced`, and expect the submitted `POST /api/transactions` body (captured by
   the stub) **not** to contain a `quantity_produced` key.
4. **Oversell is blocked client-side.** Same flow, `available_stock: '15.0000'` → type `16` into
   `Quantity Sold` → expect `/only 15 units are available/i` visible, `Save` disabled, and zero
   recorded `POST /api/transactions` calls.
5. **The three figures are labelled separately.** `/inventory` → expect column headers
   `Produced This Cycle`, `Sold This Cycle`, `Available Stock`, and the `across all cycles` caption.

- [ ] **Step 6: Gitignore the artefacts**

Append to `.gitignore`:

```
# Playwright
frontend/test-results/
frontend/playwright-report/
frontend/.playwright/
```

- [ ] **Step 7: Run the e2e suite**

```bash
cd frontend && npx playwright test
```

Expected: all specs pass. If the dev server port differs from `5173`, read it from
`frontend/vite.config.ts` and update `baseURL`/`webServer.url` to match.

- [ ] **Step 8: Commit**

```bash
git add frontend/playwright.config.ts frontend/e2e frontend/package.json \
        frontend/package-lock.json .gitignore
git commit -m "test: add Playwright e2e coverage for the inventory workflow

Network-stubbed specs covering the review gate, additive apply copy,
already-applied blocking, read-only produced quantity, client-side
oversell blocking, and the three separately-labelled figures. No
database is involved.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 18: Development-database migration and manual verification

**(R1) Execution position:** this task runs **last of all**, after Tasks 19-22. It adds no
migration of its own and the R1 tasks add none either, so the three migrations it applies are
unchanged — but its acceptance-criteria walk now covers the production series, which only exists
once Task 21 has shipped.

**Requirements covered:** closes the loop — until this runs, the feature exists only against the test
database.

**This task performs the only write to `armando_furniture` in the entire plan. Do not start it
without explicit, in-the-moment user approval.**

**Files:** none modified.

- [ ] **Step 1: Confirm the full suite is green against the test database**

```bash
cd backend && python -m pytest -q
cd frontend && npx vitest run && npx tsc -b && npx eslint src
```

- [ ] **Step 2: Back up the development database**

Ask the user to run it — `backups/` already exists in this repo for exactly this:

```
! pg_dump -h 127.0.0.1 -p 5433 -U <user> -Fc armando_furniture -f backups/pre-inventory-ledger.dump
```

- [ ] **Step 3: Show the user what will run, then ask**

```bash
cd backend && python -m alembic current && python -m alembic history -r current:head
```

Report the exact revision list. Ask: *"Apply these N migrations to armando_furniture?"* Proceed only
on an explicit yes.

- [ ] **Step 4: Apply**

```bash
cd backend && python -m alembic upgrade head
```

- [ ] **Step 5: Verify with read-only queries**

```bash
cd backend && python -m alembic current
```

Then confirm the four new tables and the new column exist, and that no existing data moved:

```
! psql -h 127.0.0.1 -p 5433 -U <user> -d armando_furniture -c "\dt opening_inventory*; \dt production_application*; \d sales_transactions"
! psql -h 127.0.0.1 -p 5433 -U <user> -d armando_furniture -c "SELECT count(*) AS sales, count(production_cycle_id) AS with_cycle FROM sales_transactions"
```

Expected: `with_cycle` is `0` — existing rows are correctly left unattributed, exactly as designed.

- [ ] **Step 6: Walk the acceptance criteria manually**

Start both servers and work through the Acceptance Criteria checklist at the end of this document,
in order. Record the result of each.

- [ ] **Step 7: Report, do not commit**

Nothing to commit. Summarise for the user: revisions applied, table/column verification output,
existing-row counts, and the acceptance-criteria results.

---

## Task 19: Ledger-sourced production data layer

**Requirements covered (revision R1):** "The production forecast must use `production_application_items` as its authoritative source for new production, while `SalesTransaction.quantity` remains the authoritative source for sales"; "Production must appear in the production series even when no sales transaction exists"; "Multiple sales must not duplicate production"; "Opening inventory must never be counted as newly produced"; "Previous-cycle production must remain historical and must not be counted again in the new cycle"; "Preserve historical forecast behaviour for pre-rollout data."

**Design note — why this lives in `forecasting.py`:** `get_transaction_historical_demand` is already the chart's *sales* data layer (one point per transaction, deliberately not the forecast algorithm's input). The production series is the same grain with the same consumer, so its reader belongs beside it, not in `production_application.py` — which stays a pure aggregate/write service (`get_cycle_produced_by_product`, `get_total_produced_by_product`) with no chart-shaped output.

**Design note — the legacy boundary:** `sales_transactions.production_cycle_id` is the discriminator between pre-rollout and post-rollout rows. Task 8's migration backfills nothing, so every row that existed before this feature has `production_cycle_id IS NULL`, and `create_transaction` (Task 10) always resolves and stores a cycle, so every row written after it is NOT NULL. That makes the boundary structural rather than date-based: a legacy row keeps reporting its stored `quantity_produced` forever, and a post-rollout row reports `None` because its production is in the ledger. Reporting both would plot the same units twice.

**Files:**
- Modify: `backend/app/services/forecasting.py:1-13` (imports), `get_transaction_historical_demand` (docstring, statement, row mapping), append `get_production_event_series`
- Test: `backend/tests/test_forecast_production_series.py` (new)

**Interfaces:**
- Consumes: `ProductionApplication`, `ProductionApplicationItem` (Task 3); `SalesTransaction.production_cycle_id` (Task 8); `save_production_application` (Task 4) in tests only; the `cleanup_applications`, `cleanup_opening_inventory` and `transaction_cycle` fixtures (moved into `conftest.py` by Tasks 4, 2 and 10).
- Produces: `get_production_event_series(db) -> dict[int, list[dict]]`, each entry `{"period": str, "application_id": int, "application_number": str, "production_cycle_id": int, "quantity_produced": Decimal}`; `get_transaction_historical_demand`'s `"quantity_produced"` becomes `Decimal | None` — the stored value for legacy rows (`production_cycle_id IS NULL`), `None` for every cycle-attributed row.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_forecast_production_series.py`:

```python
from datetime import datetime
from decimal import Decimal

from app.database.models import (
    OpeningInventoryItem,
    OpeningInventorySet,
    OptimizationRun,
    SalesTransaction,
)


def _make_run(db, cycle_id, started_at):
    run = OptimizationRun(
        production_cycle_id=cycle_id,
        started_at=started_at,
        status="OPTIMAL",
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    return run


def _apply(db, cycle_id, product_id, quantity, applied_at):
    """
    Write one ledger application, then force its applied_at:
    save_production_application stamps "now", and these tests need
    deterministic event dates on the chart's x-axis.
    """

    from app.services.production_application import (
        save_production_application,
    )

    run = _make_run(db, cycle_id, applied_at)

    application = save_production_application(
        db,
        cycle_id,
        run.id,
        {product_id: Decimal(str(quantity))},
        [],
    )

    application.applied_at = applied_at

    db.commit()
    db.refresh(application)

    return application


def _make_sale(
    db,
    product_id,
    transaction_date,
    quantity,
    quantity_produced,
    production_cycle_id,
    number,
):
    sale = SalesTransaction(
        transaction_number=number,
        product_id=product_id,
        production_cycle_id=production_cycle_id,
        transaction_date=transaction_date,
        quantity=Decimal(str(quantity)),
        quantity_produced=Decimal(str(quantity_produced)),
        unit_price=Decimal("100.00"),
        total_sales=Decimal(str(quantity)) * Decimal("100.00"),
        production_cost=Decimal("0.00"),
        unit_profit=Decimal("0.00"),
        total_profit=Decimal("0.00"),
    )

    db.add(sale)
    db.commit()
    db.refresh(sale)

    return sale


def _cleanup_sales(db, sales):
    for sale in sales:
        db.delete(sale)

    db.commit()


def test_production_event_series_has_one_point_per_application(
    db, cleanup_applications, transaction_cycle, test_products,
):
    """
    The series is sourced from the ledger, so one apply is one point -
    dated when it was applied, carrying its application number.
    """

    from app.services.forecasting import (
        get_production_event_series,
    )

    product = test_products[0]

    _apply(
        db,
        transaction_cycle.id,
        product.id,
        6,
        datetime(2026, 10, 26, 9, 0),
    )

    events = get_production_event_series(db)[product.id]

    assert len(events) == 1
    assert events[0]["period"] == "2026-10-26"
    assert events[0]["quantity_produced"] == Decimal("6")
    assert events[0]["production_cycle_id"] == transaction_cycle.id
    assert events[0]["application_number"].startswith("PA-")


def test_production_appears_with_no_sales_transaction_at_all(
    db, cleanup_applications, transaction_cycle, test_products,
):
    """
    The requirement the drawdown approach could not meet: production
    is visible on the chart before anything has been sold.
    """

    from app.services.forecasting import (
        get_production_event_series,
    )

    product = test_products[0]

    _apply(
        db,
        transaction_cycle.id,
        product.id,
        12,
        datetime(2026, 10, 26, 9, 0),
    )

    events = get_production_event_series(db)[product.id]

    assert [event["quantity_produced"] for event in events] == [
        Decimal("12"),
    ]


def test_many_sales_do_not_duplicate_one_application(
    db, cleanup_applications, transaction_cycle, test_products,
):
    """
    Production is no longer carried by sales rows, so five sales drawn
    from one applied batch still report exactly 10 produced units.
    """

    from app.services.forecasting import (
        get_production_event_series,
    )

    product = test_products[0]

    _apply(
        db,
        transaction_cycle.id,
        product.id,
        10,
        datetime(2026, 10, 26, 9, 0),
    )

    sales = [
        _make_sale(
            db,
            product.id,
            datetime(2026, 10, 27 + index),
            1,
            0,
            transaction_cycle.id,
            f"TRX-PS{index:04d}",
        )
        for index in range(5)
    ]

    try:
        events = get_production_event_series(db)[product.id]

        assert sum(
            event["quantity_produced"] for event in events
        ) == Decimal("10")

    finally:
        _cleanup_sales(db, sales)


def test_opening_inventory_is_never_reported_as_produced(
    db, cleanup_applications, cleanup_opening_inventory,
    transaction_cycle, test_products,
):
    """
    Opening inventory is a starting balance, not production. The
    series joins production_application_items only - it must not know
    opening_inventory_items exists.
    """

    from app.services.forecasting import (
        get_production_event_series,
    )

    product = test_products[0]

    inventory_set = OpeningInventorySet(
        set_number="OI-PS01",
        status="REVIEWED",
        effective_date=datetime(2026, 10, 1),
        reviewed_at=datetime(2026, 10, 1),
    )

    db.add(inventory_set)
    db.flush()

    db.add(
        OpeningInventoryItem(
            opening_inventory_set_id=inventory_set.id,
            product_id=product.id,
            quantity=Decimal("40"),
        )
    )

    db.commit()

    _apply(
        db,
        transaction_cycle.id,
        product.id,
        6,
        datetime(2026, 10, 26, 9, 0),
    )

    events = get_production_event_series(db)[product.id]

    assert sum(
        event["quantity_produced"] for event in events
    ) == Decimal("6")


def test_previous_cycle_production_stays_on_its_own_date(
    db, cleanup_applications, test_products,
):
    """
    Last cycle's production is history: it keeps its own point and its
    own cycle id, and is never re-counted into the new cycle's point.
    """

    from app.database.models import ProductionCycle
    from app.services.forecasting import (
        get_production_event_series,
    )

    product = test_products[0]

    first = ProductionCycle(
        cycle_date=datetime(2026, 10, 11),
        start_date=datetime(2026, 10, 11),
        end_date=datetime(2026, 10, 18),
        status="CLOSED",
    )

    second = ProductionCycle(
        cycle_date=datetime(2026, 10, 18),
        start_date=datetime(2026, 10, 18),
        end_date=datetime(2026, 10, 25),
        status="OPEN",
    )

    db.add_all([first, second])
    db.commit()
    db.refresh(first)
    db.refresh(second)

    try:
        _apply(
            db,
            first.id,
            product.id,
            8,
            datetime(2026, 10, 12, 9, 0),
        )
        _apply(
            db,
            second.id,
            product.id,
            5,
            datetime(2026, 10, 19, 9, 0),
        )

        events = get_production_event_series(db)[product.id]

        assert [
            (
                event["period"],
                event["production_cycle_id"],
                event["quantity_produced"],
            )
            for event in events
        ] == [
            ("2026-10-12", first.id, Decimal("8")),
            ("2026-10-19", second.id, Decimal("5")),
        ]

    finally:
        db.delete(second)
        db.delete(first)
        db.commit()


def test_inactive_products_are_excluded(
    db, cleanup_applications, transaction_cycle, test_products,
):
    """
    Same qualification rule as the sales layer, so a product can never
    appear in one series and be missing from the other.
    """

    from app.services.forecasting import (
        get_production_event_series,
    )

    product = test_products[0]

    _apply(
        db,
        transaction_cycle.id,
        product.id,
        6,
        datetime(2026, 10, 26, 9, 0),
    )

    product.is_active = False
    db.commit()

    try:
        assert product.id not in get_production_event_series(db)

    finally:
        product.is_active = True
        db.commit()


def test_legacy_sale_keeps_reporting_its_stored_produced_quantity(
    db, test_products,
):
    """
    Pre-rollout rows have production_cycle_id NULL and no ledger entry
    anywhere. Their stored quantity_produced is the only production
    record they will ever have, so the sales layer must keep handing
    it to the chart byte-for-byte.
    """

    from app.services.forecasting import (
        get_transaction_historical_demand,
    )

    product = test_products[0]

    sale = _make_sale(
        db,
        product.id,
        datetime(2026, 8, 23),
        1,
        5,
        None,
        "TRX-PS9001",
    )

    try:
        history = get_transaction_historical_demand(db)[product.id]

        assert history[0]["quantity_produced"] == Decimal("5")

    finally:
        _cleanup_sales(db, [sale])


def test_cycle_attributed_sale_reports_no_produced_quantity(
    db, transaction_cycle, test_products,
):
    """
    A post-rollout row's production lives in the ledger. Reporting its
    stored quantity_produced here too would plot the same units twice.
    """

    from app.services.forecasting import (
        get_transaction_historical_demand,
    )

    product = test_products[0]

    sale = _make_sale(
        db,
        product.id,
        datetime(2026, 10, 27),
        1,
        6,
        transaction_cycle.id,
        "TRX-PS9002",
    )

    try:
        history = get_transaction_historical_demand(db)[product.id]

        assert history[0]["quantity"] == Decimal("1")
        assert history[0]["quantity_produced"] is None

    finally:
        _cleanup_sales(db, [sale])
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_forecast_production_series.py -q
```

Expected: `ImportError: cannot import name 'get_production_event_series'` for the first six, and an
`assert Decimal('6') is None` failure for `test_cycle_attributed_sale_reports_no_produced_quantity`.

- [ ] **Step 3: Extend the model imports in `backend/app/services/forecasting.py`**

Replace the import block at the top of the file:

```python
from app.database.models import (
    Product,
    ProductionApplication,
    ProductionApplicationItem,
    SalesTransaction,
)
```

- [ ] **Step 4: Make the sales layer report produced for legacy rows only**

In `get_transaction_historical_demand`, replace the final paragraph of the docstring:

```python
    Returns, per product_id, a list of
    {"period": "YYYY-MM-DD", "transaction_id": int,
     "transaction_number": str, "quantity": Decimal,
     "quantity_produced": Decimal | None} ordered by
    (transaction_date, id), so transactions sharing a date stay
    separate and keep a stable identity.

    "quantity_produced" is reported ONLY for pre-rollout rows -
    the ones with production_cycle_id IS NULL, written before the
    production application ledger existed. Their stored figure is
    the only production record they have, so the chart must keep
    rendering it exactly as it always did. Every cycle-attributed
    row reports None: its production is in the ledger, and
    get_production_event_series() is the authoritative source for
    it. Reporting both would plot the same units twice.
    """
```

Add `SalesTransaction.production_cycle_id` to the `select(...)` column list, immediately after
`SalesTransaction.quantity_produced`, and replace the row mapping's produced entry:

```python
                "quantity_produced": (
                    row.quantity_produced
                    if row.production_cycle_id is None
                    else None
                ),
```

- [ ] **Step 5: Append `get_production_event_series` after `get_transaction_historical_demand`**

```python
def get_production_event_series(
    db: Session,
) -> dict[int, list[dict]]:
    """
    Return every applied production event per active product, one
    point per (production application, product), chronologically.

    This is the production counterpart of
    get_transaction_historical_demand(): the chart's production data
    layer. production_application_items is the authoritative source
    for new production - never ProductionAllocation (a plan, replaced
    wholesale on every apply), never SalesTransaction.quantity_produced
    (a cost attribution that only exists once something is sold), and
    never opening_inventory_items (a starting balance that was never
    produced here).

    Because every application row is its own event, production appears
    exactly once, on the date it was applied: ten sales cannot
    duplicate it, zero sales cannot hide it, and a previous cycle's
    application keeps its own date instead of being counted again in
    the current cycle.

    Qualification mirrors the sales layer (active product, positive
    quantity) so a product can never appear in one series and be
    missing from the other.

    Returns, per product_id, a list of
    {"period": "YYYY-MM-DD", "application_id": int,
     "application_number": str, "production_cycle_id": int,
     "quantity_produced": Decimal} ordered by
    (applied_at, application_id).
    """

    statement = (
        select(
            ProductionApplicationItem.product_id,
            ProductionApplicationItem.quantity_produced,
            ProductionApplication.id.label("application_id"),
            ProductionApplication.application_number,
            ProductionApplication.production_cycle_id,
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
        .order_by(
            ProductionApplicationItem.product_id,
            ProductionApplication.applied_at,
            ProductionApplication.id,
        )
    )

    events: dict[int, list[dict]] = defaultdict(list)

    for row in db.execute(statement).all():
        events[row.product_id].append(
            {
                "period": row.applied_at.strftime("%Y-%m-%d"),
                "application_id": row.application_id,
                "application_number": row.application_number,
                "production_cycle_id": row.production_cycle_id,
                "quantity_produced": row.quantity_produced,
            }
        )

    return dict(events)
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_forecast_production_series.py -q
```

Expected: PASS.

- [ ] **Step 7: Verify the existing forecast suites are untouched**

```bash
cd backend && python -m pytest tests/test_forecast.py tests/test_forecast_aggregation.py \
  tests/test_forecast_timeseries.py tests/test_forecast_history.py -q
```

Expected: all pass with **no edits to those files**. Every transaction they build leaves
`production_cycle_id` unset, so they are legacy rows by construction and keep reporting their stored
produced figures. **If any of them fails, stop** — the legacy boundary is wrong, not the test.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/forecasting.py \
        backend/tests/test_forecast_production_series.py
git commit -m "feat: read new production from the application ledger

The chart's production data layer now comes from
production_application_items, so production is visible without a sale,
cannot be duplicated by several sales, and never includes opening
inventory. Pre-rollout sales rows keep reporting their stored
quantity_produced; cycle-attributed rows no longer do.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 20: Production points in the forecast timeseries

**Requirements covered (revision R1):** the same six as Task 19, at the API boundary — plus "`SalesTransaction.quantity` remains the authoritative source for sales" (untouched here) and "preserve historical forecast behaviour for pre-rollout data" (the forecast anchor must stay byte-identical when no ledger rows exist).

**Design note — one axis, three point kinds:** the response stays a single flat `series` per product because the chart's x-axis is a category domain built from it in API order (see `ForecastChart.tsx`'s `AXIS_KEY_SEPARATOR` comment). A new explicit `point_type` discriminator (`SALE` / `PRODUCTION` / `FORECAST`) carries the meaning; `is_forecast` keeps its exact current value so nothing that already reads it breaks. A production point sorts **before** a same-day sale: units must exist before they are sold, and a fixed tie-break is what makes the ordering reproducible.

**Files:**
- Modify: `backend/app/services/forecasting.py` (add the three `POINT_TYPE_*` constants, `_POINT_TYPE_SORT_RANK`, `_timeseries_sort_key`, rewrite `get_forecast_timeseries`'s assembly)
- Modify: `backend/app/schemas/forecast.py` (`ForecastTimeSeriesPoint`: four new fields)
- Test: `backend/tests/test_forecast_timeseries_production.py` (new)

**Interfaces:**
- Consumes: `get_production_event_series`, `get_transaction_historical_demand` (Task 19).
- Produces: `POINT_TYPE_SALE = "SALE"`, `POINT_TYPE_PRODUCTION = "PRODUCTION"`, `POINT_TYPE_FORECAST = "FORECAST"` in `app.services.forecasting`; `ForecastTimeSeriesPoint` gains `point_type: str`, `application_id: int | None = None`, `application_number: str | None = None`, `production_cycle_id: int | None = None`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_forecast_timeseries_production.py`:

```python
from datetime import datetime

# Plain module name, not "tests.test_...": pytest's default (prepend)
# import mode puts backend/tests on sys.path, so this is the import
# form that does not also depend on how the runner was invoked.
from test_forecast_production_series import (
    _apply,
    _cleanup_sales,
    _make_sale,
)


def _series(client, product_id):
    response = client.get(
        "/api/forecast/timeseries",
        params={"product_id": product_id},
    )

    assert response.status_code == 200

    return response.json()["products"][0]["series"]


def test_timeseries_carries_a_production_point_per_application(
    client, db, cleanup_applications, transaction_cycle, test_products,
):
    """
    The ledger's apply event reaches the chart as its own point, with
    no sales transaction involved anywhere.
    """

    product = test_products[0]

    _apply(
        db,
        transaction_cycle.id,
        product.id,
        6,
        datetime(2026, 10, 26, 9, 0),
    )

    series = _series(client, product.id)

    production = [
        point
        for point in series
        if point["point_type"] == "PRODUCTION"
    ]

    assert len(production) == 1
    assert production[0]["period"] == "2026-10-26"
    assert production[0]["quantity_produced"] == "6.0000"
    assert production[0]["historical_sales"] is None
    assert production[0]["is_forecast"] is False
    assert production[0]["transaction_id"] is None
    assert production[0]["application_number"].startswith("PA-")


def test_production_only_product_still_gets_one_forecast_point(
    client, db, cleanup_applications, transaction_cycle, test_products,
):
    """
    With production but no sales, the series is one production point
    plus exactly one forecast point - anchored on the month AFTER the
    apply, so the forecast still sorts last.
    """

    product = test_products[0]

    _apply(
        db,
        transaction_cycle.id,
        product.id,
        6,
        datetime(2026, 10, 26, 9, 0),
    )

    series = _series(client, product.id)

    assert [point["point_type"] for point in series] == [
        "PRODUCTION",
        "FORECAST",
    ]
    assert series[-1]["period"] == "2026-11-01"
    assert series[-1]["is_forecast"] is True


def test_a_production_point_sorts_before_a_same_day_sale(
    client, db, cleanup_applications, transaction_cycle, test_products,
):
    """
    Units have to exist before they can be sold, and a fixed tie-break
    keeps the x-axis order reproducible across requests.
    """

    product = test_products[0]

    _apply(
        db,
        transaction_cycle.id,
        product.id,
        6,
        datetime(2026, 10, 27, 9, 0),
    )

    sale = _make_sale(
        db,
        product.id,
        datetime(2026, 10, 27),
        2,
        6,
        transaction_cycle.id,
        "TRX-TP0001",
    )

    try:
        series = _series(client, product.id)

        assert [point["point_type"] for point in series] == [
            "PRODUCTION",
            "SALE",
            "FORECAST",
        ]
        # The sale reports sold only: its production is the ledger's.
        assert series[1]["historical_sales"] == "2.0000"
        assert series[1]["quantity_produced"] is None

    finally:
        _cleanup_sales(db, [sale])


def test_chronological_order_interleaves_both_kinds(
    client, db, cleanup_applications, transaction_cycle, test_products,
):
    """
    Two kinds of event, one axis, strictly by date.
    """

    product = test_products[0]

    _apply(
        db,
        transaction_cycle.id,
        product.id,
        6,
        datetime(2026, 10, 26, 9, 0),
    )

    sales = [
        _make_sale(
            db,
            product.id,
            datetime(2026, 10, 28),
            2,
            0,
            transaction_cycle.id,
            "TRX-TP0002",
        ),
        _make_sale(
            db,
            product.id,
            datetime(2026, 10, 30),
            1,
            0,
            transaction_cycle.id,
            "TRX-TP0003",
        ),
    ]

    try:
        series = _series(client, product.id)

        assert [
            (point["period"], point["point_type"])
            for point in series
        ] == [
            ("2026-10-26", "PRODUCTION"),
            ("2026-10-28", "SALE"),
            ("2026-10-30", "SALE"),
            ("2026-11-01", "FORECAST"),
        ]

    finally:
        _cleanup_sales(db, sales)


def test_legacy_sale_point_keeps_its_produced_figure_and_type(
    client, db, test_products,
):
    """
    Pre-rollout behaviour, pinned at the API boundary: a legacy row is
    a SALE point that still carries the produced value the user typed.
    """

    product = test_products[0]

    sale = _make_sale(
        db,
        product.id,
        datetime(2026, 8, 23),
        1,
        5,
        None,
        "TRX-TP0004",
    )

    try:
        series = _series(client, product.id)

        assert series[0]["point_type"] == "SALE"
        assert series[0]["quantity_produced"] == "5.0000"
        assert series[0]["application_id"] is None

    finally:
        _cleanup_sales(db, [sale])
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_forecast_timeseries_production.py -q
```

Expected: `KeyError: 'point_type'` on every test.

- [ ] **Step 3: Add the four fields to `ForecastTimeSeriesPoint`**

In `backend/app/schemas/forecast.py`, replace the `ForecastTimeSeriesPoint` comment block and body:

```python
class ForecastTimeSeriesPoint(BaseModel):
    # point_type is the authoritative kind discriminator:
    #   SALE       - one qualifying sales transaction. "period" is the
    #                transaction date (YYYY-MM-DD), transaction_id/
    #                transaction_number identify the row, and
    #                historical_sales carries the quantity SOLD.
    #                quantity_produced is set only on PRE-ROLLOUT rows
    #                (those with no production_cycle_id) - see
    #                services/forecasting.py for why.
    #   PRODUCTION - one applied production ledger entry. "period" is
    #                the apply date, application_id/
    #                application_number/production_cycle_id identify
    #                it, and quantity_produced carries the units
    #                PRODUCED. This is the authoritative source for
    #                new production.
    #   FORECAST   - the single trailing projection. "period" is the
    #                first day of the forecasted month.
    # is_forecast is kept, unchanged, for every existing consumer: it
    # is True exactly when point_type == "FORECAST".
    period: str
    point_type: str
    transaction_id: int | None = None
    transaction_number: str | None = None
    application_id: int | None = None
    application_number: str | None = None
    production_cycle_id: int | None = None
    historical_sales: Decimal | None = None
    quantity_produced: Decimal | None = None
    predicted_demand: Decimal | None = None
    is_forecast: bool
```

- [ ] **Step 4: Add the point-type constants and sort key to `forecasting.py`**

Insert directly above `get_forecast_timeseries`:

```python
POINT_TYPE_SALE = "SALE"
POINT_TYPE_PRODUCTION = "PRODUCTION"
POINT_TYPE_FORECAST = "FORECAST"

# A production event on the same calendar day as a sale sorts first:
# the units have to exist before they can be sold, and a fixed
# tie-break is what keeps the x-axis order identical across requests
# (the chart uses the series order as its category domain).
_POINT_TYPE_SORT_RANK = {
    POINT_TYPE_PRODUCTION: 0,
    POINT_TYPE_SALE: 1,
}


def _timeseries_sort_key(point: dict) -> tuple:
    return (
        point["period"],
        _POINT_TYPE_SORT_RANK[point["point_type"]],
        point["application_id"]
        or point["transaction_id"]
        or 0,
    )
```

- [ ] **Step 5: Rewrite `get_forecast_timeseries`'s assembly**

Replace the docstring's second and third paragraphs with:

```python
    Historical points come from two independent sources, merged onto
    one chronological axis: one SALE point per qualifying sales
    transaction (get_transaction_historical_demand()) and one
    PRODUCTION point per applied ledger entry
    (get_production_event_series()). Sales are authoritative for
    quantity SOLD, the ledger is authoritative for quantity PRODUCED,
    and neither is ever derived from the other - which is why
    production shows up with no sale recorded, and why several sales
    drawn from one applied batch cannot report that batch twice.

    The forecast is still computed from monthly SOLD totals only
    (calculate_forecast() over get_monthly_historical_demand()), never
    re-derived from either series. The single trailing FORECAST point
    is anchored on the month after the product's latest event of
    either kind, so it always sorts last; with no ledger rows that is
    the last transaction month, exactly as before this feature
    existed. A product with no events at all has no historical points
    and its forecast point falls on the month after today.
    """
```

Then replace everything from `monthly_historical_demand = ...` down to the final
`return {"products": product_series}` with:

```python
    monthly_historical_demand = get_monthly_historical_demand(db)
    forecasts = calculate_forecast(monthly_historical_demand)
    historical_transactions = get_transaction_historical_demand(db)
    production_events = get_production_event_series(db)

    products_statement = (
        select(Product)
        .where(Product.is_active.is_(True))
        .order_by(Product.id)
    )

    if product_id is not None:
        products_statement = products_statement.where(
            Product.id == product_id
        )

    products = list(db.scalars(products_statement).all())

    today = date.today()

    product_series = []

    for product in products:
        history = historical_transactions.get(product.id, [])
        production = production_events.get(product.id, [])
        forecast = forecasts.get(
            product.id,
            {"forecast_quantity": Decimal("0")},
        )

        sale_points = [
            {
                "period": item["period"],
                "point_type": POINT_TYPE_SALE,
                "transaction_id": item["transaction_id"],
                "transaction_number": item[
                    "transaction_number"
                ],
                "application_id": None,
                "application_number": None,
                "production_cycle_id": None,
                "historical_sales": item["quantity"],
                "quantity_produced": item[
                    "quantity_produced"
                ],
                "predicted_demand": None,
                "is_forecast": False,
            }
            for item in history
        ]

        production_points = [
            {
                "period": event["period"],
                "point_type": POINT_TYPE_PRODUCTION,
                "transaction_id": None,
                "transaction_number": None,
                "application_id": event["application_id"],
                "application_number": event[
                    "application_number"
                ],
                "production_cycle_id": event[
                    "production_cycle_id"
                ],
                "historical_sales": None,
                "quantity_produced": event[
                    "quantity_produced"
                ],
                "predicted_demand": None,
                "is_forecast": False,
            }
            for event in production
        ]

        points = sorted(
            production_points + sale_points,
            key=_timeseries_sort_key,
        )

        if points:
            last_year, last_month = (
                int(part)
                for part in points[-1]["period"].split("-")[:2]
            )
            forecast_year, forecast_month = _next_month(
                last_year,
                last_month,
            )
        else:
            forecast_year, forecast_month = _next_month(
                today.year,
                today.month,
            )

        points.append(
            {
                "period": (
                    f"{forecast_year:04d}-{forecast_month:02d}-01"
                ),
                "point_type": POINT_TYPE_FORECAST,
                "transaction_id": None,
                "transaction_number": None,
                "application_id": None,
                "application_number": None,
                "production_cycle_id": None,
                "historical_sales": None,
                "quantity_produced": None,
                "predicted_demand": forecast[
                    "forecast_quantity"
                ],
                "is_forecast": True,
            }
        )

        product_series.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "series": points,
            }
        )

    return {"products": product_series}
```

- [ ] **Step 6: Run the new tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_forecast_timeseries_production.py -q
```

Expected: PASS.

- [ ] **Step 7: Verify the existing forecast suites are still green, unchanged**

```bash
cd backend && python -m pytest tests/test_forecast.py tests/test_forecast_aggregation.py \
  tests/test_forecast_timeseries.py tests/test_forecast_history.py \
  tests/test_forecast_chat.py -q
```

Expected: all pass with **no edits to those files**. They build legacy rows and assert sold values,
point counts and ordering — all unchanged. This step is the formal check on "preserve historical
forecast behaviour for pre-rollout data": a failure here means the merge changed pre-rollout output
and must be fixed in `forecasting.py`, never by relaxing those tests.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/forecast.py backend/app/services/forecasting.py \
        backend/tests/test_forecast_timeseries_production.py
git commit -m "feat: add ledger production points to the forecast timeseries

GET /api/forecast/timeseries now merges SALE points (authoritative for
units sold) with PRODUCTION points read from the application ledger
(authoritative for units produced) on one chronological axis, and
anchors the forecast point on the latest event of either kind. Output
for pre-rollout data is unchanged.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 21: Frontend — the production series on the forecast chart

**Requirements covered (revision R1):** "Production must appear in the production series even when no sales transaction exists" (the visible half); "preserve historical forecast behaviour for pre-rollout data" (legacy produced figures stay exactly where they were — in the tooltip).

**Design note — plotted vs. tooltip:** the plotted production series is **ledger-only**. Today `quantity_produced` is not plotted at all (`forecastTypes.ts`: "carried for display only"), so leaving legacy figures in the tooltip *is* the preserved behaviour; promoting them into the new line would retroactively change how settled history reads. Mantine's `LineChart` defaults `connectNulls` to `true` (verified in `@mantine/charts/cjs/LineChart/LineChart.cjs`), so the production line joins its points straight across the sale rows between them instead of fragmenting.

**Files:**
- Modify: `frontend/src/pages/demand-forecasting/api/forecastTypes.ts`
- Modify: `frontend/src/pages/demand-forecasting/types.ts`
- Modify: `frontend/src/pages/demand-forecasting/api/forecastAdapter.ts:170-193`
- Modify: `frontend/src/pages/demand-forecasting/components/ForecastChart.tsx`
- Test: `frontend/src/pages/demand-forecasting/api/forecastAdapter.test.ts` (append), `frontend/src/pages/demand-forecasting/components/ForecastChart.test.tsx` (create — follow `ResourcesPage.test.tsx` for the provider wrapper)

**Interfaces:**
- Consumes: Task 20's wire contract (`point_type`, `application_number`, `quantity_produced`).
- Produces: `ForecastPointType = 'SALE' | 'PRODUCTION' | 'FORECAST'`; `ForecastChartData` gains `pointType: ForecastPointType`, `producedQuantity?: number`, `applicationNumber?: string`; `quantityProduced?: number` keeps its current name and its tooltip-only role.

- [ ] **Step 1: Write the failing adapter test**

Append to `frontend/src/pages/demand-forecasting/api/forecastAdapter.test.ts`:

```ts
describe('toUiForecastChartData production points', () => {
  it('plots produced units from PRODUCTION points only', () => {
    const rows = toUiForecastChartData({
      products: [
        {
          product_id: 1,
          product_name: 'Door',
          series: [
            {
              period: '2026-10-26',
              point_type: 'PRODUCTION',
              transaction_id: null,
              transaction_number: null,
              application_id: 7,
              application_number: 'PA-0007',
              production_cycle_id: 3,
              historical_sales: null,
              quantity_produced: '6.0000',
              predicted_demand: null,
              is_forecast: false,
            },
            {
              period: '2026-10-28',
              point_type: 'SALE',
              transaction_id: 9,
              transaction_number: 'TRX-000009',
              application_id: null,
              application_number: null,
              production_cycle_id: null,
              historical_sales: '2.0000',
              quantity_produced: null,
              predicted_demand: null,
              is_forecast: false,
            },
          ],
        },
      ],
    })

    expect(rows[0].pointType).toBe('PRODUCTION')
    expect(rows[0].producedQuantity).toBe(6)
    expect(rows[0].applicationNumber).toBe('PA-0007')
    expect(rows[0].historicalDemand).toBeUndefined()

    expect(rows[1].producedQuantity).toBeUndefined()
    expect(rows[1].historicalDemand).toBe(2)
  })

  it('keeps a legacy sale point produced figure in the tooltip field', () => {
    const rows = toUiForecastChartData({
      products: [
        {
          product_id: 1,
          product_name: 'Door',
          series: [
            {
              period: '2026-08-23',
              point_type: 'SALE',
              transaction_id: 1,
              transaction_number: 'TRX-000001',
              application_id: null,
              application_number: null,
              production_cycle_id: null,
              historical_sales: '1.0000',
              quantity_produced: '5.0000',
              predicted_demand: null,
              is_forecast: false,
            },
          ],
        },
      ],
    })

    expect(rows[0].quantityProduced).toBe(5)
    expect(rows[0].producedQuantity).toBeUndefined()
  })
})
```

The existing fixtures in this file and in `useForecast.test.tsx` / `DemandForecastingPage.test.tsx`
build points without `point_type`; add `point_type: 'SALE'` (and `'FORECAST'` on each forecast point)
plus the three new `null` fields to every one of them so they still satisfy the type. Do not change
any of their assertions.

- [ ] **Step 2: Run it to verify it fails**

```bash
cd frontend && npx vitest run src/pages/demand-forecasting/api/forecastAdapter.test.ts
```

Expected: FAIL — `pointType` and `producedQuantity` are not on `ForecastChartData`, and the fixtures
do not type-check against `ForecastTimeSeriesPoint`.

- [ ] **Step 3: Extend the wire and UI types**

In `forecastTypes.ts`, replace the `quantity_produced is carried for display only` comment paragraph
and the interface with:

```ts
// point_type is the authoritative kind discriminator (see
// backend/app/schemas/forecast.py):
//   SALE       - one sales transaction; historical_sales is the
//                quantity SOLD, the measure the forecast is built
//                from. quantity_produced is set only on PRE-ROLLOUT
//                rows, is display-only, and is NOT plotted.
//   PRODUCTION - one applied production ledger entry;
//                quantity_produced is the quantity PRODUCED and is
//                the plotted production value. No transaction.
//   FORECAST   - the single trailing projection.
// is_forecast stays available and is True exactly when point_type is
// 'FORECAST'.
export type ForecastPointType = 'SALE' | 'PRODUCTION' | 'FORECAST'

export interface ForecastTimeSeriesPoint {
  period: string
  point_type: ForecastPointType
  transaction_id: number | null
  transaction_number: string | null
  application_id: number | null
  application_number: string | null
  production_cycle_id: number | null
  historical_sales: string | null
  quantity_produced: string | null
  predicted_demand: string | null
  is_forecast: boolean
}
```

In `types.ts`, replace the `ForecastChartData` tooltip-context block with:

```ts
  // Which kind of event this row is - see forecastTypes.ts. The
  // tooltip branches on this rather than on which value is defined.
  pointType: ForecastPointType
  // Tooltip-only context.
  transactionNumber?: string
  applicationNumber?: string
  // Pre-rollout produced figure carried by a SALE row. Display only,
  // never plotted - that is how it has always rendered.
  quantityProduced?: number
  // The PLOTTED production value, set only on a PRODUCTION row. Its
  // source is the production application ledger.
  producedQuantity?: number
```

and add the import at the top of `types.ts`:

```ts
import type { ForecastPointType } from './api/forecastTypes'
```

- [ ] **Step 4: Map the new fields in the adapter**

Replace the `return series.map(...)` body in `toUiForecastChartData`:

```ts
  return series.map((point) => ({
    date: formatAxisLabel(point.period),
    fullDate: formatFullDate(point.period),
    pointType: point.point_type,
    isForecast: point.is_forecast,
    transactionNumber: point.transaction_number ?? undefined,
    applicationNumber: point.application_number ?? undefined,
    // Plotted production comes from the ledger's PRODUCTION points
    // only. A legacy SALE row's produced figure stays tooltip-only,
    // exactly as it rendered before the ledger existed - promoting it
    // into the line would retroactively redraw settled history.
    producedQuantity:
      point.point_type === 'PRODUCTION'
        ? parseNullableDecimal(point.quantity_produced)
        : undefined,
    quantityProduced:
      point.point_type === 'SALE'
        ? parseNullableDecimal(point.quantity_produced)
        : undefined,
    historicalDemand: point.is_forecast
      ? undefined
      : parseNullableDecimal(point.historical_sales),
    forecastedDemand: point.is_forecast
      ? parseNullableDecimal(point.predicted_demand)
      : undefined,
  }))
```

- [ ] **Step 5: Run the adapter test to verify it passes**

```bash
cd frontend && npx vitest run src/pages/demand-forecasting/api/forecastAdapter.test.ts
```

Expected: PASS.

- [ ] **Step 6: Write the failing chart test**

Create `frontend/src/pages/demand-forecasting/components/ForecastChart.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'
import { describe, expect, it } from 'vitest'

import ForecastChart from './ForecastChart'
import type { ForecastChartData } from '../types'

const renderChart = (data: ForecastChartData[]) =>
  render(
    <MantineProvider>
      <ForecastChart
        data={data}
        isLoading={false}
        isError={false}
        hasProducts
      />
    </MantineProvider>,
  )

const productionRow: ForecastChartData = {
  date: 'Oct 26',
  fullDate: 'Oct 26, 2026',
  pointType: 'PRODUCTION',
  isForecast: false,
  applicationNumber: 'PA-0007',
  producedQuantity: 6,
}

const forecastRow: ForecastChartData = {
  date: 'Nov 01',
  fullDate: 'Nov 01, 2026',
  pointType: 'FORECAST',
  isForecast: true,
  forecastedDemand: 4,
}

describe('ForecastChart', () => {
  it('renders the chart when a product has production but no sales', () => {
    renderChart([productionRow, forecastRow])

    expect(
      screen.queryByText(/No sales history for this product yet/),
    ).not.toBeInTheDocument()
    expect(screen.getByText('Applied Production')).toBeInTheDocument()
  })

  it('still explains an entirely empty product', () => {
    renderChart([forecastRow])

    expect(
      screen.getByText(/No sales or production recorded/),
    ).toBeInTheDocument()
  })
})
```

- [ ] **Step 7: Run it to verify it fails**

```bash
cd frontend && npx vitest run src/pages/demand-forecasting/components/ForecastChart.test.tsx
```

Expected: FAIL — the empty-state guard short-circuits on a production-only product, so
`No sales history for this product yet` renders and `Applied Production` is absent.

- [ ] **Step 8: Add the production series to the chart**

In `ForecastChart.tsx`:

1. Add the series key beside the existing two:

```tsx
const PRODUCED_SERIES = 'producedQuantity'
```

2. Replace the `hasHistoricalPoints` guard with one that accepts either kind of event, and widen the
   copy (a production-only product now renders a real chart):

```tsx
  // A product with nothing recorded still gets exactly one forecast
  // point (a flat 0-unit projection) from
  // GET /api/forecast/timeseries, which renders as an empty-looking
  // chart. Production alone IS plottable now - the ledger reports it
  // whether or not anything has been sold - so only a product with
  // neither sales nor production gets the explanatory message.
  const hasPlottablePoints = data.some(
    (point) =>
      point.historicalDemand !== undefined ||
      point.producedQuantity !== undefined,
  )

  if (!hasPlottablePoints) {
    return (
      <Center h={280}>
        <Text c="dimmed" ta="center">
          No sales or production recorded for this product yet.
          Record sales transactions or apply a production plan, then
          run the demand forecast to see historical and forecasted
          demand.
        </Text>
      </Center>
    )
  }
```

3. Branch the tooltip on `pointType`, replacing the `row.isForecast ? ... : ...` ternary:

```tsx
      {row.pointType === 'FORECAST' && (
        <Text size="xs" c="dimmed">
          Forecasted demand: {row.forecastedDemand ?? 0} units
        </Text>
      )}

      {row.pointType === 'PRODUCTION' && (
        <>
          <Text size="xs" c="dimmed">
            Applied production: {row.producedQuantity ?? 0} units
          </Text>
          {row.applicationNumber && (
            <Text size="xs" c="dimmed">
              {row.applicationNumber}
            </Text>
          )}
        </>
      )}

      {row.pointType === 'SALE' && (
        <>
          <Text size="xs" c="dimmed">
            Quantity sold: {row.historicalDemand ?? 0} units
          </Text>
          {/* Pre-rollout rows only - see types.ts. */}
          {row.quantityProduced !== undefined && (
            <Text size="xs" c="dimmed">
              Quantity produced: {row.quantityProduced} units
            </Text>
          )}
          {row.transactionNumber && (
            <Text size="xs" c="dimmed">
              {row.transactionNumber}
            </Text>
          )}
        </>
      )}
```

4. Register the third series. `teal` is distinct from both themes' primary (`wood` / `blue`) and
   from the forecast's `grape`/`blue`, so production never reads as demand on either theme:

```tsx
      series={[
        {
          name: HISTORICAL_SERIES,
          label: 'Historical Demand (Transaction)',
        },
        {
          name: PRODUCED_SERIES,
          label: 'Applied Production',
          color: 'teal.6',
        },
        {
          name: FORECAST_SERIES,
          label: 'Forecasted Demand',
          color: forecastColor,
          strokeDasharray: '6 6',
        },
      ]}
```

Leave `lastHistoricalIndex`, `chartData`, `renderForecastDot` and `xAxisProps` exactly as they are:
the forecast point is still the last row, production rows carry no `historicalDemand` so they cannot
become the dashed line's anchor, and `connectNulls` (Mantine's default `true`) joins the production
points across the sale rows between them.

- [ ] **Step 9: Run the chart and page tests to verify they pass**

```bash
cd frontend && npx vitest run src/pages/demand-forecasting
```

Expected: PASS, including `DemandForecastingPage.test.tsx` and `useForecast.test.tsx` with only the
fixture additions from Step 1.

- [ ] **Step 10: Typecheck, lint and build**

```bash
cd frontend && npx tsc -b && npx eslint src/pages/demand-forecasting && npm run build
```

Expected: clean.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/pages/demand-forecasting
git commit -m "feat: plot applied production on the demand forecast chart

Production points from the application ledger render as their own teal
series, so production is visible with no sale recorded and is never
duplicated by several sales. Pre-rollout produced figures stay in the
tooltip, where they have always been.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 22: Source-of-truth guardrails (test-only)

**Requirements covered (revision R1):** "Confirm that manual allocation CRUD does not create inventory. Only a successful Apply operation should record finished-goods production."

**Why a task and not a footnote:** the confirmation is already true in today's code —
`services/allocation.py::create_allocation` / `update_allocation` / `delete_allocation` write
`ProductionAllocation` rows and nothing else, and after Task 6 the only caller of
`save_production_application` is `apply_optimization`. But "nothing else writes the ledger" is
exactly the kind of invariant a later change breaks silently, and it is cheap to pin. This task adds
no production code.

**Files:**
- Test: `backend/tests/test_inventory_source_of_truth.py` (new)

**Interfaces:**
- Consumes: `create_allocation`, `update_allocation`, `delete_allocation` (existing); `get_available_stock_for_product` (Task 9); `ProductionApplication`, `ProductionApplicationItem` (Task 3).
- Produces: nothing.

- [ ] **Step 1: Write the tests**

Create `backend/tests/test_inventory_source_of_truth.py`:

```python
from decimal import Decimal
from pathlib import Path

from app.database.models import (
    ProductionApplication,
    ProductionApplicationItem,
)
from app.schemas.allocation import (
    ProductionAllocationCreate,
    ProductionAllocationUpdate,
)
from app.services.allocation import (
    create_allocation,
    delete_allocation,
    update_allocation,
)
from app.services.inventory import get_available_stock_for_product


def _ledger_counts(db):
    return (
        db.query(ProductionApplication).count(),
        db.query(ProductionApplicationItem).count(),
    )


def test_manual_allocation_crud_creates_no_inventory(
    db, cleanup_applications, transaction_cycle, test_products,
    test_product_resource_requirements,
):
    """
    ProductionAllocation is a PLAN. Only a successful apply records
    finished-goods production, so planning by hand must leave both the
    ledger and available stock untouched - create, update and delete.
    """

    product = test_products[0]

    before_counts = _ledger_counts(db)
    before_stock = get_available_stock_for_product(db, product.id)

    allocation = create_allocation(
        db,
        transaction_cycle.id,
        ProductionAllocationCreate(
            product_id=product.id,
            quantity=Decimal("5"),
        ),
    )

    assert _ledger_counts(db) == before_counts
    assert get_available_stock_for_product(
        db, product.id,
    ) == before_stock

    update_allocation(
        db,
        allocation,
        ProductionAllocationUpdate(quantity=Decimal("9")),
    )

    assert _ledger_counts(db) == before_counts
    assert get_available_stock_for_product(
        db, product.id,
    ) == before_stock

    delete_allocation(db, allocation)

    assert _ledger_counts(db) == before_counts
    assert get_available_stock_for_product(
        db, product.id,
    ) == before_stock


def test_apply_optimization_is_the_only_ledger_writer():
    """
    Grep-as-a-test: save_production_application must stay called from
    exactly one place. If this fails a new write path appeared, and the
    "only a successful apply records production" guarantee needs
    re-checking - not this assertion relaxing.

    production_application.py is listed because it holds the
    definition itself. Run from backend/, where the rest of the suite
    runs from.
    """

    services = Path("app/services")

    callers = sorted(
        path.name
        for path in services.glob("*.py")
        if "save_production_application(" in path.read_text(
            encoding="utf-8",
        )
    )

    assert callers == [
        "optimization.py",
        "production_application.py",
    ]
```

If `transaction_cycle`'s window has no `CycleResource` rows,
`_validate_proposed_allocation_capacity` raises before the allocation is written — reuse
`optimization_cycle` instead (it configures resources) and keep the same assertions. Decide by
reading `conftest.py`'s two fixtures before running.

- [ ] **Step 2: Run them**

```bash
cd backend && python -m pytest tests/test_inventory_source_of_truth.py -q
```

Expected: PASS immediately — these pin existing behaviour rather than drive new code. If
`test_manual_allocation_crud_creates_no_inventory` fails, an earlier task introduced an inventory
side-effect into the planning path and that is a bug in that task. If
`test_apply_optimization_is_the_only_ledger_writer` fails, read the new caller before touching the
assertion.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_inventory_source_of_truth.py
git commit -m "test: pin that only a successful apply records production

Manual allocation CRUD is planning, not production: it must leave the
application ledger and available stock untouched. Also pins
save_production_application to a single call site.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---


# Deliverable 1 — Final database schema and relationships

## New tables

```
opening_inventory_sets
  id                      PK
  set_number              varchar(20)  NOT NULL UNIQUE          "OI-0001"
  status                  varchar(20)  NOT NULL DEFAULT 'DRAFT' DRAFT|REVIEWED|SUPERSEDED
  effective_date          timestamp    NOT NULL
  notes                   varchar(500) NULL
  created_at              timestamp    NOT NULL
  created_by_user_id      FK users.id        ON DELETE SET NULL  NULL
  reviewed_at             timestamp    NULL
  reviewed_by_user_id     FK users.id        ON DELETE SET NULL  NULL
  -- partial unique index: at most ONE row with status = 'REVIEWED'
  UNIQUE INDEX uq_opening_inventory_single_reviewed (status) WHERE status = 'REVIEWED'

opening_inventory_items
  id                           PK
  opening_inventory_set_id     FK opening_inventory_sets.id  ON DELETE CASCADE
  product_id                   FK products.id                ON DELETE CASCADE
  quantity                     numeric(12,4) NOT NULL
  notes                        varchar(500)  NULL
  UNIQUE (opening_inventory_set_id, product_id)   uq_opening_inventory_item

production_applications
  id                     PK
  application_number     varchar(20) NOT NULL UNIQUE            "PA-0001"
  production_cycle_id    FK production_cycles.id  ON DELETE CASCADE
  optimization_run_id    FK optimization_runs.id  ON DELETE CASCADE
  applied_at             timestamp   NOT NULL
  UNIQUE (optimization_run_id)   uq_production_application_run   ← duplicate-apply guard

production_application_items
  id                           PK
  production_application_id    FK production_applications.id  ON DELETE CASCADE
  product_id                   FK products.id                 ON DELETE CASCADE
  quantity_produced            numeric(12,4) NOT NULL
  UNIQUE (production_application_id, product_id)   uq_production_application_item

production_application_resource_items
  id                           PK
  production_application_id    FK production_applications.id  ON DELETE CASCADE
  resource_id                  FK resources.id   ON DELETE SET NULL   NULL
  resource_name                varchar(100)  NOT NULL     ← denormalised at write time
  unit                         varchar(30)   NOT NULL     ← denormalised at write time
  consumed_quantity            numeric(12,4) NOT NULL
  UNIQUE (production_application_id, resource_id)
      uq_production_application_resource_item
```

## Changed table

```
sales_transactions
  + production_cycle_id   FK production_cycles.id  ON DELETE SET NULL  NULL, INDEXED
```

Nullable and never backfilled. All-time sold (and therefore available stock) ignores this column
entirely, so a legacy row still reduces stock; only the per-cycle sold breakdown excludes it.

## Unchanged tables (explicitly)

`products` (no `stock_quantity` — ever), `production_allocations` (same columns, same
`uq_production_allocation`, same delete-then-reinsert on apply), `cycle_resources`,
`optimization_runs`, `optimization_results`, `resource_utilization_runs`,
`resource_utilization_history_items`, `forecast_runs`, `forecast_results`, `products`/`resources`
catalogues.

## Relationship map

```
ProductionCycle 1──* ProductionAllocation            (current plan — replaced each apply)
ProductionCycle 1──* OptimizationRun 1──* OptimizationResult
ProductionCycle 1──* ProductionApplication           (ledger — append-only, accumulates)
ProductionCycle 1──* ResourceUtilizationRun 1──* ResourceUtilizationHistoryItem
ProductionCycle 1──* SalesTransaction                (new, nullable)

OptimizationRun 1──0..1 ProductionApplication        (UNIQUE — applied at most once)

ProductionApplication 1──* ProductionApplicationItem          → produced units  (stock input)
ProductionApplication 1──* ProductionApplicationResourceItem  → consumed capacity (incremental input)

OpeningInventorySet 1──* OpeningInventoryItem        (exactly one set is REVIEWED)
Product 1──* OpeningInventoryItem / ProductionApplicationItem / SalesTransaction
```

**Why this shape and not the alternatives:**

- *A `stock_quantity` column on `products`* — rejected. `PATCH` and `DELETE /api/transactions/{id}`
  both exist, so a stored counter needs a correct compensating reversal on every edit and delete and
  drifts permanently the first time one is missed. A derived sum cannot drift. (Task 11's
  `test_deleting_a_sale_returns_stock` is the test that proves the derived design handles this for
  free.)
- *Making `ProductionAllocation` cumulative* — rejected. Four consumers read it as the current plan
  (`check_allocation_feasibility`, `calculate_resource_consumption`,
  `get_allocations_with_financials`, the utilization snapshot), and `uq_production_allocation`
  structurally forbids two rows per product per cycle anyway.
- *Resolving an unmatched transaction date to the latest cycle* — rejected by requirement, and
  rightly: it silently corrupts that cycle's reported sales.

---

# Deliverable 2 — Alembic migration sequence

Current single head: **`c7a1e4d9f2b8`** (`add_optimization_run_history_flags`). Verify with
`python -m alembic heads` before starting — the chain must stay linear.

| Order | Task | Message | `down_revision` | Contents |
|---|---|---|---|---|
| 1 | Task 1 | `add opening inventory` | `c7a1e4d9f2b8` | `opening_inventory_sets`, `opening_inventory_items`, the partial unique index |
| 2 | Task 3 | `add production application ledger` | ← rev 1 | `production_applications`, `production_application_items`, `production_application_resource_items` |
| 3 | Task 8 | `add production cycle to sales transactions` | ← rev 2 | `sales_transactions.production_cycle_id` + index + FK |

Three migrations, strictly additive: no column is dropped, altered, or backfilled, and no existing
row is touched. Every `downgrade()` is written and reversible.

**Execution order, every time:** test database first (`DATABASE_URL="$TEST_DATABASE_URL" alembic
upgrade head`), run the suite, and only reach `armando_furniture` in Task 18 after a `pg_dump` and
explicit user approval.

---

# Deliverables 3 & 4 — Backend and frontend implementation sequence

The task list above **is** the sequence. Dependencies are strictly left-to-right; nothing may be
reordered across a dependency arrow.

**Backend (Deliverable 3):**

```
Task 0  test-database isolation            ← HARD PREREQUISITE for everything
  │
  ├── Task 1  opening inventory models + migration
  │     └── Task 2  opening inventory service / schemas / API (review gate)
  │
  ├── Task 3  ledger models + migration
  │     └── Task 4  ledger service (write path + aggregates)
  │           ├── Task 5  incremental capacity offset
  │           │     └── Task 6  rewire apply_optimization   ←┐ mutual: Task 6 Step 6
  │           ├── Task 7  cumulative utilization snapshot   ←┘ needs Task 7 Step 3
  │           └── Task 8  sales_transactions.production_cycle_id + cycle resolution
  │
  └── Tasks 2 + 4 + 8 ──> Task 9   inventory derivation + GET /api/inventory
                            └── Task 10  transaction create (auto-fill, validation, lock)
                                  └── Task 11  transaction update/delete + zero-produced fix
```

**Frontend (Deliverable 4):** starts only after Task 9 ships the `/api/inventory` contract.

```
Task 12  API layers (inventory + opening inventory)
  ├── Task 13  Opening Stock page (setup + review)        [needs Task 2]
  ├── Task 14  Inventory page (three distinct figures)    [needs Task 9]
  ├── Task 15  Add Transaction modal (read-only produced, stock cap)  [needs Tasks 10, 11]
  └── Task 16  Production Allocation (additive copy, already-applied) [needs Task 6]
        └── Task 17  Playwright e2e  ← needs Tasks 13-16 on screen
```

**Forecast source, R1 (Deliverable 9):** independent of Tasks 9-17 — it needs only the ledger and
the sales cycle column.

```
Tasks 3 + 8 ──> Task 19  ledger-sourced production data layer (forecasting.py)
                  └── Task 20  production points in GET /api/forecast/timeseries
                        └── Task 21  frontend production series on the chart

Tasks 3 + 6 + 9 ──> Task 22  source-of-truth guardrails (test-only, no production code)

Task 22 ──> Task 18  dev-database migration + manual verification  ← LAST, gated on approval
```

Task 19 needs Task 8's `sales_transactions.production_cycle_id` column to exist (it reads it as
the legacy marker) and Task 4's `save_production_application` for its fixtures — but it does **not**
need Tasks 9-11, so the R1 chain can run in parallel with the inventory and transaction work once
Task 8 is in. Task 21 needs Task 20's wire contract and nothing else on the frontend. Task 22 is
test-only and needs Task 9's `get_available_stock_for_product` plus Task 6's rewired apply.

A reviewer can reject any single task without blocking its siblings. Tasks 13-16 are mutually
independent and could run in parallel if you choose subagent-driven execution; so are the two R1
chains (19→20→21 and 22).

---

# Deliverable 5 — Forecast source and compatibility strategy

**Revised by R1.** The original strategy made the chart's produced figure a *drawdown* of
`SalesTransaction.quantity_produced`. That kept the per-cycle total honest, but it tied production
reporting to sales: with no sale, production was invisible; with several sales, the figure was
spread across rows by order of entry. The forecast now reads production from the ledger directly.

## Where each number comes from

| Consumer | Source | Effect of this plan |
|---|---|---|
| `get_monthly_historical_demand` (lines ~45-77) — the forecast algorithm's input | `SalesTransaction.quantity` (sold) | **None.** Not touched by any task. |
| `get_transaction_historical_demand` — the chart's SALE points | `SalesTransaction.quantity` (sold) | **None** for the plotted value. |
| The chart's produced figure on a **pre-rollout** SALE point | `SalesTransaction.quantity_produced` where `production_cycle_id IS NULL` | **None.** Still tooltip-only, still the stored value. |
| The chart's **production series** (new) | `production_application_items` joined to `production_applications` | New: one plotted point per apply event. |
| Per-transaction `production_cost` / `total_profit` | `SalesTransaction.quantity_produced` (drawdown-filled) | Unchanged from the original plan. |

Sales are authoritative for units **sold**. The ledger is authoritative for units **produced**.
Neither is derived from the other, and `ProductionAllocation` feeds neither.

## Six guarantees, and the mechanism behind each

1. **Production appears with no sales transaction.** The production series is a query over
   `production_application_items`; `sales_transactions` is not in it. Pinned by Task 19's
   `test_production_appears_with_no_sales_transaction_at_all` and Task 20's
   `test_production_only_product_still_gets_one_forecast_point`.

2. **Multiple sales cannot duplicate production.** The plotted produced value no longer rides on
   sales rows at all, so the sales count is arithmetically irrelevant. Pinned by
   `test_many_sales_do_not_duplicate_one_application`.

3. **Opening inventory is never counted as production.** `opening_inventory_items` is a different
   table and appears in no production query. Pinned by
   `test_opening_inventory_is_never_reported_as_produced` with 40 opening units against 6 produced.

4. **Previous-cycle production stays historical.** Every ledger item belongs to exactly one
   application, which carries one `applied_at` and one `production_cycle_id`. A point is drawn at
   its own apply date and never re-emitted, so a new cycle starts with no inherited production.
   Pinned by `test_previous_cycle_production_stays_on_its_own_date`.

5. **Pre-rollout forecast output is frozen.** No task backfills, updates or recomputes any existing
   `quantity_produced`, and `production_cycle_id IS NULL` is the structural marker that keeps legacy
   rows reporting their stored figure (Task 11's R1 guard stops an edit from reclassifying one).
   `test_forecast.py`, `test_forecast_aggregation.py`, `test_forecast_timeseries.py` and
   `test_forecast_history.py` are run **unedited** at Task 19 Step 7 and Task 20 Step 7 — they are
   the regression harness, because every row they build is a legacy row by construction.

6. **Sold-quantity semantics are untouched.** `SalesTransaction.quantity` keeps its exact meaning
   and is still entirely user-supplied, so historical demand, trend and confidence outputs are
   unaffected. The forecast is still computed from monthly sold totals only.

## What `quantity_produced` is now

A **compatibility and costing column**, retained deliberately:

- It drives `calculate_transaction_values`' production cost, and therefore `production_cost`,
  `unit_profit` and `total_profit` on every transaction. Nothing else can supply that today.
- It is the produced figure the chart shows for pre-rollout rows, which is what freezes historical
  behaviour.
- It is still displayed and exported in Transaction History.
- It is still auto-filled by Task 10's drawdown and still read-only in the UI, so the spec
  requirement "do not require users to manually enter or synchronize the produced quantity" holds.

The drawdown therefore survives, with its justification narrowed: it is no longer what keeps the
chart honest (the ledger does that), it is what keeps the column from overstating production.
Task 10, Task 15 and Task 16 are unchanged.

## The one visible change, stated plainly

For cycles recorded after this change, the chart gains a teal **Applied Production** line with a
point per apply event, and cycle-attributed sale points stop showing a produced figure in their
tooltip (their production is on that line instead). Pre-rollout points render exactly as they do
today. The produced total under the curve now equals real applied production rather than whatever
was typed per row.

## Known boundary artifact (accepted, not fixed)

In the first cycle after rollout, a product can have both pre-rollout sale points carrying typed
produced figures *and* a ledger production point from a later apply. Both are displayed, because
the alternative is rewriting or suppressing settled history — which the Global Constraints forbid.
The figures describe different events (an untracked past production vs. a recorded apply), and the
overlap disappears as soon as the cycle turns over.

## Deliberately out of scope

No change to `ForecastRun`/`ForecastResult`, to `forecast_chat.py`, or to the forecast algorithm.
No change to how `production_cost` is computed. If the business later wants per-transaction cost to
follow units **sold** (standard cost-of-goods-sold) rather than attributed production, that is a
separate accounting decision — it would relax the "Σ `quantity_produced` ≤ cycle production"
constraint, and it is now *possible* only because the forecast no longer reads the column. Recorded
here as a follow-up, not implemented.

---

# Deliverable 6 — Concurrency and transaction-safety strategy

Available stock is a **derived sum**, which means no row-level constraint can reject an oversell —
there is nothing in `sales_transactions` to constrain, because the rows being summed do not exist
yet. Safety therefore comes from three layers, each covering what the others cannot.

## Layer 1 — Database constraints (absolute, cannot be raced)

| Constraint | Prevents |
|---|---|
| `uq_production_application_run` | The same optimization run ever producing two ledger rows — the double-counted-units bug — even under two simultaneous requests. |
| `uq_opening_inventory_single_reviewed` (partial) | Two reviewed opening balances, which would make every stock figure ambiguous. |
| `uq_production_application_item` / `..._resource_item` | A malformed application with two rows for one product/resource. |
| `uq_production_allocation` (existing) | Unchanged — the current plan stays one row per product. |

## Layer 2 — Row locks (serialise read-check-write)

| Lock | Taken in | Protects |
|---|---|---|
| `SELECT … FROM production_cycles WHERE id = :id FOR UPDATE` | `apply_optimization` (Task 6, first statement) | Two concurrent applies in one cycle each reading the same already-consumed offset, both passing the capacity check, and both appending — which the `optimization_run_id` constraint would *not* catch if the two requests carried different runs. |
| `SELECT products.id WHERE id = :id FOR UPDATE` | `create_transaction` and `update_transaction` (Tasks 10, 11, before the stock read) | Two concurrent sales of the same product each reading stock `10`, each finding room for `10`, and both committing. Locks `products` rather than the sales rows because the protected quantity is a sum over rows that do not exist yet. |

Both locks are taken **before** the figure they protect is read and held until the request's
`commit()`/`rollback()`. Different products take different locks and never block each other.

## Layer 3 — Single-transaction atomicity

`apply_optimization` performs all five writes in **one** transaction, committing exactly once:

1. `DELETE` the cycle's `ProductionAllocation` rows
2. `INSERT` the new `ProductionAllocation` rows
3. `db.flush()` — so step 5's `SELECT` sees them (project-wide `autoflush=False`, see
   `app/database/connection.py`)
4. `INSERT` the `ProductionApplication` + both item sets (`save_production_application` deliberately
   does not commit)
5. `INSERT` the `ResourceUtilizationRun` + items (`save_resource_utilization_history` likewise)

Any failure rolls all five back. Task 6's `test_a_rejected_apply_leaves_no_ledger_row` proves it:
a capacity rejection must leave zero ledger rows, or stock would count units that were never
produced.

Every capacity and duplicate check also runs **before** the `DELETE` in step 1 — a rejected apply
never disturbs the existing allocation. This ordering already existed for the capacity check; this
plan keeps it and adds the duplicate guard to the same pre-write block.

## What is explicitly *not* guaranteed

- **Two different cycles applying simultaneously** are independent by design — they draw on
  different `CycleResource` rows, so no cross-cycle lock is needed or taken.
- **Stock can still read negative in pre-existing data** (a legacy sale of stock the ledger never
  recorded). `get_available_stock` floors at zero so no screen reports negative physical goods;
  validation prevents *new* sales from creating that state. This is a reporting floor, not a
  pretence that the data is clean.
- **`db.query(...).delete()` plus `with_for_update()` in the same session** relies on SQLAlchemy's
  session-level ordering, not on `SERIALIZABLE` isolation. The default isolation level is unchanged;
  the locks above are what provide the ordering, and raising isolation is explicitly not part of
  this plan.

---

# Deliverable 7 — Complete test plan

## Backend — pytest (new files)

| File | Count | Covers |
|---|---|---|
| `tests/test_database_isolation.py` | 1 | Engine is bound to `armando_furniture_test` (Task 0) |
| `tests/test_opening_inventory.py` | 10 | Persistence, single-reviewed index, one item per product, DRAFT→REVIEWED gate, reviewed set immutable, supersede-not-mutate, draft excluded from derivation, duplicate/negative rejection, `/active`, auth |
| `tests/test_production_application.py` | 8 | Item persistence, duplicate-run `IntegrityError`, two applications per cycle, no-commit contract, cycle + all-cycles aggregates, `has_application_for_run`, zero-quantity skip, cycle scoping |
| `tests/test_incremental_capacity.py` | 3 | Offset deducted, availability floored at zero, no-offset path byte-identical |
| `tests/test_production_apply_ledger.py` | 8 | Generate writes nothing, apply appends with both item sets, duplicate run → 400, second run accumulates, second apply without capacity → 400, `ProductionAllocation` still one-row-per-product, rejected apply leaves nothing, `/applications` endpoint |
| `tests/test_transaction_cycle_resolution.py` | 8 | Inside-window, inclusive start, half-open end, no-match → reject, overlap → reject, created row carries cycle, create rejects unmatched date, legacy NULL preserved |
| `tests/test_inventory.py` | 8 | `opening + produced − sold`, opening-only, draft excluded, cycle totals reset while stock carries, drawdown, drawdown floored, `/api/inventory` three figures, auth |
| `tests/test_transaction_stock.py` | 15 | Auto-fill from ledger, second sale records 0, produced ≠ stock, oversell → 400, exact-stock sale, **the full Day 1/3/5 scenario**, gate-off passthrough, concurrent oversell, update oversell → 400, update no self-double-count, lowering returns stock, delete returns stock, zero-produced edit does not crash, update to unmatched date → 400, **(R1)** editing a pre-rollout row leaves it unattributed |
| `tests/test_forecast_production_series.py` **(R1)** | 8 | One point per application, production with no sale, many sales do not duplicate, opening inventory excluded, previous cycle keeps its own date, inactive products excluded, legacy row keeps its stored produced figure, cycle-attributed row reports none |
| `tests/test_forecast_timeseries_production.py` **(R1)** | 5 | PRODUCTION point in the API response, production-only product still gets one forecast point, production sorts before a same-day sale, both kinds interleave chronologically, legacy SALE point unchanged |
| `tests/test_inventory_source_of_truth.py` **(R1)** | 2 | Manual allocation CRUD creates no inventory, `save_production_application` has exactly one call site |

**Modified backend tests:** `tests/conftest.py` (test-DB guard, `cleanup_applications`,
`cleanup_opening_inventory`, `transaction_cycle`, `two_cycles`); `tests/test_transactions.py`
(replace `test_create_transaction_rejects_invalid_quantity_produced`, rework
`test_production_cost_uses_quantity_produced_not_sold`, add cycles to every POST);
`tests/test_transaction_date_filter.py` (add cycles); `tests/test_resource_utilization.py` (+2
override tests); `tests/test_business_endpoint_protection.py` (two new routers).

**Must still pass untouched:** `test_optimization.py`, `test_optimization_history_lifecycle.py`,
`test_allocations.py`, `test_minimum_demand.py`, `test_forecast*.py` (all four — **the R1
regression harness: never edit these to make a task pass**),
`test_resource_utilization_history.py`, `test_products.py`, `test_resources.py`, `test_auth.py`,
`test_dashboard.py`.

## Frontend — vitest + RTL

| File | Covers |
|---|---|
| `inventory/api/inventoryAdapter.test.ts` (3) | Decimal-string parsing, gate/cycle passthrough, no-cycle response |
| `opening-inventory/OpeningInventoryPage.test.tsx` (3) | "not yet enforced" warning, product rows, review requires confirmation |
| `inventory/InventoryPage.test.tsx` (2) | Three columns are separate, "across all cycles" caption |
| `transaction-history/components/AddTransactionModal.test.tsx` (+5) | Produced read-only and auto-filled, available stock shown, oversell blocks Save, no cap while gate off, payload omits `quantity_produced` |
| `production-allocation/hooks/useProductionAllocation.test.tsx` (+2) | `['inventory']` invalidated after apply, already-applied blocks `canApply` |
| `production-allocation/ProductionAllocationPage.test.tsx` (+2) | Additive apply copy (and absence of the old "replace" copy), already-applied explanation |
| `demand-forecasting/api/forecastAdapter.test.ts` (+2) **(R1)** | PRODUCTION point maps to the plotted `producedQuantity`; a legacy SALE point's figure stays in the tooltip field |
| `demand-forecasting/components/ForecastChart.test.tsx` (2) **(R1)** | A production-only product renders the chart with an Applied Production series; a product with neither sales nor production still shows the explanatory message |

## Playwright — `frontend/e2e/`

Network-stubbed, no database involved.

| Spec | Scenarios |
|---|---|
| `opening-inventory.spec.ts` | Gate advertised as off; review requires confirmation then fires |
| `production-cycle.spec.ts` | Additive apply copy; already-applied blocks Apply; produced read-only + omitted from payload; client-side oversell blocked with zero POSTs; three figures labelled separately on `/inventory` |

## Gaps this plan knowingly does not test

- Multi-process true concurrency (Task 10's test uses two sessions in one process — it proves the
  validation rejects the second sale, not that PostgreSQL blocked it). A genuine race test needs two
  OS processes and is not worth the flake; the row lock plus the unique constraints are the
  argument.
- Load/perf of `get_available_stock` at scale (see Risk 7).
- A Playwright run against a real backend (deliberate — it would need a database).

---

# Deliverable 8 — Risks, assumptions, and acceptance criteria

## Risks

1. **Manual allocation CRUD keeps non-incremental capacity checks.**
   `services/allocation.py::_validate_proposed_allocation_capacity` still calls
   `find_resource_capacity_shortages` with no offset, so `POST`/`PATCH
   /api/production-cycles/{id}/allocations` would let a manual allocation exceed capacity already
   consumed by the ledger. *Mitigation:* no UI calls those endpoints (confirmed in
   `productionApi.ts`: "read-only in this integration"), and they are auth-protected. *Follow-up:*
   pass the offset there too, as a small separate change — deliberately excluded here to keep this
   plan's blast radius on the apply path.

2. **The second apply in a cycle needs resources topped up.** Incremental consumption is what the
   user approved, and it means the Day-5 apply fails unless `CycleResource.available_quantity` was
   raised. The error message names the resource, the shortfall, and says previous applications
   consumed part of the capacity — but this *will* be a new support question. Task 6's
   `test_a_second_apply_without_fresh_capacity_is_rejected` locks the behaviour in.

3. **Existing sales become invisible to per-cycle reporting.** `production_cycle_id` is NULL for
   every pre-migration row, so cycle-scoped sold starts from zero while all-time sold (and stock)
   includes them. *This is the intended trade* — the alternative is fabricating cycle attribution —
   but the Inventory page's `Sold This Cycle` will understate history for the current cycle if it
   contains pre-migration sales.

4. **The 7-day cycle is still entirely manual.** Nothing creates cycles on a schedule
   (`seed.py:306` is the only place `timedelta(days=7)` appears). If no cycle covers today, **every
   new transaction is rejected** — a much louder failure than before. *Mitigation:* the error names
   the date and tells the user to create a cycle. *Follow-up worth considering:* a cycle-rollover
   job, or a warning banner when no cycle covers today.

5. **Half-open `[start, end)` changes nothing today but is a real decision.** Under it, `seed.py`'s
   `start + 7 days` is exactly 7 days and back-to-back cycles never overlap. A user who hand-creates
   a cycle with `end_date == start_date` gets a zero-day window that matches nothing. *Follow-up:*
   tighten `validate_cycle_dates` from `end >= start` to `end > start`.

6. **Soft-deleted products retain stock.** `delete_product` only sets `is_active = False`, and
   `get_inventory_overview` filters to active products — so a deactivated product's stock silently
   vanishes from the Inventory page while still existing in the derivation. Products have no
   permanent-delete path (the `c70e38d` feature is resources-only), so the cascade on
   `Product.sales_transactions` is not currently reachable.

7. **`get_available_stock` is three unindexed-by-product aggregate queries per call,** and
   `get_inventory_overview` calls that family six times. Fine at this data scale; worth a single
   grouped query or a materialised view if `sales_transactions` reaches six figures.

8. **`Numeric(12,4)` quantities vs integer units.** `apply_optimization` casts
   `int(result.recommended_quantity)`, so ledger quantities are whole, but the columns permit
   fractions and the API accepts them for sales. Fractional furniture is nonsense; no task rejects
   it. *Follow-up:* a whole-units validator mirroring `schemas/product.py::_require_whole_units`.

9. **Three new user-facing routes** (`/opening-inventory`, `/inventory`) and two new nav entries
   grow the sidebar from 7 to 9 items. Worth a glance at `Sidebar.tsx` spacing on a short viewport.

## Assumptions

1. `armando_furniture_test` can be created on `127.0.0.1:5433` with the same credentials as
   `armando_furniture`, and migrating it is acceptable.
2. The business wants **physical** stock tracked (units that exist), not committed/available-to-promise
   stock. No reservation concept is introduced.
3. Opening inventory is declared **once** per product, for the whole business, not per warehouse or
   per location.
4. A reviewed opening balance may be corrected by a superseding set, and recomputing every stock
   figure from the new balance is the desired outcome of that correction.
5. `quantity_produced` on a transaction is a *record of production attribution*, not an editable
   business input — which is why updates do not re-derive it.
6. Sales are only ever recorded through `POST /api/transactions`; nothing writes
   `sales_transactions` directly.
7. The optimizer's recommended quantities remain whole numbers (they do today —
   `int(result.recommended_quantity)`).
8. Playwright may be added as a frontend devDependency.

## Acceptance criteria

**Production ledger**
- [ ] Generating a plan changes no stock figure and writes no `production_applications` row.
- [ ] Apply appends exactly one `production_applications` row with per-product produced quantities and per-resource consumed quantities.
- [ ] Applying the same optimization run twice returns 400 and leaves the ledger unchanged.
- [ ] A second, different plan applied in the same cycle **adds** to that cycle's produced total.
- [ ] `ProductionAllocation` still holds one row per product, replaced on each apply.
- [ ] A rejected apply leaves no ledger row, no changed allocation, and no utilization snapshot.

**Incremental capacity**
- [ ] A second apply with no added capacity is rejected, naming the resource and the shortfall.
- [ ] A second apply after capacity is increased succeeds.
- [ ] The Resource Utilization report for a cycle with two applications shows cumulative consumption.

**Opening inventory**
- [ ] With no reviewed set, `/api/inventory` reports `stock_validation_enabled: false` and sales are accepted without stock checks.
- [ ] A draft's quantities do not affect any stock figure.
- [ ] Reviewing a draft switches validation on; the set becomes uneditable.
- [ ] Reviewing a second set supersedes the first, which remains readable.
- [ ] Opening inventory alone **is** available stock before any production or sales (not zero).

**Stock derivation**
- [ ] `available_stock == opening + Σ applied production − Σ sales`, across all cycles.
- [ ] **Day 1/3/5:** apply 10 → 10; sell 5 → 5; apply 10 → **15**.
- [ ] A new cycle shows `cycle_produced == 0` and `cycle_sold == 0` while `available_stock` is unchanged.
- [ ] `available_stock` is never reported negative.

**Sales validation**
- [ ] A sale above available stock returns 400 naming the available quantity; no row is created.
- [ ] A sale of exactly the available stock succeeds and leaves stock at 0.
- [ ] Raising an existing sale above available stock returns 400 (not 500); the stored row is unchanged.
- [ ] An update that keeps the same quantity, or lowers it, is never rejected by self-double-counting.
- [ ] Deleting a sale returns its units to available stock.
- [ ] Editing a transaction whose `quantity_produced` is 0 returns 200, not a 500.

**Cycle attribution**
- [ ] A transaction dated inside a cycle stores that `production_cycle_id`.
- [ ] A transaction dated outside every cycle returns 400 naming the date — never assigned to the latest cycle.
- [ ] A date matching two overlapping cycles returns 400 naming both.
- [ ] Pre-migration rows keep `production_cycle_id = NULL` and still count toward stock.

**Forecast compatibility**
- [ ] All four forecast test files pass unchanged, with no edits.
- [ ] `Σ quantity_produced` within a cycle equals that cycle's applied production.
- [ ] No existing `quantity_produced` value is rewritten by any migration or code path.
- [ ] A pre-rollout sales row still shows its stored produced figure in the chart tooltip, and an
      edit to that row leaves `production_cycle_id` NULL.

**Forecast production series (R1)**
- [ ] Applying a plan puts a production point on the chart at the apply date, with **no sales
      transaction recorded for that product**.
- [ ] Recording five sales against one applied batch leaves the production series showing that
      batch exactly once, at its original quantity.
- [ ] 40 units of reviewed opening inventory plus an apply of 6 shows a production point of 6 —
      opening inventory appears nowhere in the production series.
- [ ] Last cycle's apply keeps its own dated point; the new cycle's point carries only the new
      cycle's production.
- [ ] A second apply in the same cycle adds a second production point rather than replacing the
      first.
- [ ] A product with production but no sales renders a real chart, not the "no history" message;
      a product with neither still shows the explanatory message.
- [ ] A production point's tooltip names its application number; a cycle-attributed sale point's
      tooltip shows sold units only.
- [ ] Creating, editing and deleting an allocation by hand changes no production point and no
      available-stock figure.

**UI**
- [ ] Quantity Produced is read-only, auto-filled, and absent from the create payload.
- [ ] Quantity Sold is capped at available stock, with Save disabled on an oversell — only while validation is enabled.
- [ ] The Apply modal says it **adds** units to the cycle; the "replace the current committed allocation" copy is gone.
- [ ] An already-applied plan disables Apply and explains why.
- [ ] The Inventory page labels produced-this-cycle, sold-this-cycle, and available-stock-across-all-cycles as three distinct figures.

**Safety**
- [ ] `pytest` aborts if `DATABASE_URL` is not `armando_furniture_test`.
- [ ] No migration ran against `armando_furniture` before Task 18's backup and explicit approval.
- [ ] `git status` shows no changes outside the files this plan names, and the five pre-existing untracked directories are intact.

---

# Deliverable 9 — Revision R1: execution groups and checkpoints

## Why the forecast source changed (decision record)

The drawdown was sound arithmetic for one purpose — keeping `Σ quantity_produced` per cycle equal to
real production — but it made production reporting a function of sales:

| Requirement | Drawdown | Ledger-sourced |
|---|---|---|
| Production visible with no sale | ✗ invisible until the first sale | ✓ one point per apply |
| Several sales cannot duplicate production | ✓ (by construction) | ✓ (sales are not the source) |
| Opening inventory never counted as production | ✓ | ✓ (different table, never joined) |
| Previous-cycle production not re-counted | ✓ (cycle-filtered) | ✓ (per-application date + cycle) |
| Pre-rollout behaviour preserved | ✓ | ✓ (`production_cycle_id IS NULL` marker) |
| Production attributable to an event | ✗ attributed to whichever sale came first | ✓ named application |

**Cost of the change:** three new tasks and one test-only task (19-22), four new fields on
`ForecastTimeSeriesPoint`, one new frontend series, and a three-line guard in Task 11. No new
migration, no new table, no change to Tasks 0-10 or 12-17, and no data rewrite. That is a bounded
increase, so the change is made rather than deferred.

**What was *not* changed, and why:** `quantity_produced` keeps its drawdown auto-fill. It is load-
bearing for `production_cost`/`total_profit` and it is the frozen produced figure for pre-rollout
rows. Removing or re-defining it (for example filling it with units sold) would change costing
semantics and break the Global Constraint that a cycle's `Σ quantity_produced` cannot exceed that
cycle's applied production — a separate decision, recorded as a follow-up in Deliverable 5.

## Manual allocation CRUD creates no inventory — confirmed

Verified against the current code, not assumed:

- `services/allocation.py::create_allocation` validates capacity, inserts one `ProductionAllocation`
  row, commits. `update_allocation` validates and sets `quantity`. `delete_allocation` deletes the
  row. None of the three touches any other table.
- `ProductionAllocation` is a **plan**, and no derivation in this plan reads it: available stock is
  `opening + Σ ledger produced − Σ sales sold`, and the production series reads
  `production_application_items`.
- After Task 6, `save_production_application` is called from exactly one place:
  `optimization.py::apply_optimization`, inside its single transaction, after every guard
  (`OPTIMAL`, not summary-only, has results, no existing application for the run, capacity
  available). A rejected apply writes nothing.
- Task 22 pins both halves as tests so a later change cannot break it silently.

One caveat, already recorded as Risk 1 and unchanged by R1: manual allocation CRUD still validates
capacity *non-incrementally*, so a hand-written allocation can exceed capacity the ledger has
already consumed. It still creates no inventory — it only lets a plan be unrealistic. No UI calls
those endpoints.

## Task groups and review checkpoints

Subagent-driven execution, one fresh subagent per task, **review after every group**. A group is
rejected or accepted as a whole; a rejected task is re-dispatched before the group's checkpoint is
signed off.

| Group | Tasks | Gate to enter | Checkpoint — reviewer must see |
|---|---|---|---|
| **G0 Safety** | 0 | — | `pytest` prints `armando_furniture_test`; the suite refuses to run against dev. **Nothing else starts until this is signed off.** |
| **G1 Foundations** | 1, 2, 3 | G0 | Two migrations on the test DB, single head, linear chain; opening-inventory review gate enforced; ledger's `UNIQUE(optimization_run_id)` rejects a duplicate run. |
| **G2a Ledger service** | 4, **24** | G1 | `save_production_application` does not commit; cycle and all-cycles aggregates correct. **[AMENDMENT B]** Task 24: `purge_ledger` scoped signature, five-table FK order preserved, `all_rows=True` only from designated clean-slate fixtures, sentinel row survives a full suite run, R-A fixed in `test_optimization_history_lifecycle.py`. **Task 4 first, then Task 24 — both before G2.** |
| **G2 Apply path** | 5, **7, 6** | G2a | Apply appends one application + both item sets; duplicate run → 400; second apply without fresh capacity → 400; `ProductionAllocation` still one row per product; utilization snapshot cumulative. **[AMENDMENT E] Order is 5 → 7 → 6, strictly sequential. Tasks 6 and 7 must NOT run as parallel implementations** — Task 6 consumes Task 7's `consumption_override` kwarg. |
| **G2b Opening inventory gate** | **23** | G1 | **[AMENDMENT A]** Review refuses an incomplete set (400 naming undeclared products); a sale with no complete reviewed set is refused (409); `OpeningInventoryItem`/`get_opening_quantities` docstrings corrected; Task 10's skip test inverted. Completeness = products with `is_active IS TRUE` **and** `created_at <= effective_date` (A.1 ruling). **Blocks G4. A.1 is RULED — no longer blocked.** |
| **G3 Cycle attribution** | 8 | G1 | Third migration applied; `with_cycle = 0` on existing rows; half-open window rule enforced; unmatched date → 400. |
| **G4 Inventory + sales** | 9, 10, 11 | G2 + G3 + **G2b** | Day 1/3/5 scenario (10 → sell 5 → apply 10 → **15**); oversell → 400 on create *and* update; zero-produced edit returns 200; **R1:** editing a pre-rollout row leaves `production_cycle_id` NULL. |
| **G5 Forecast source (R1)** | 19, 20 | G3 (+ Task 4) | Production point with no sale; five sales do not duplicate one batch; 40 opening + 6 applied → 6; previous cycle keeps its own date; **all four forecast test files pass unedited**. |
| **G6 Frontend data + pages** | 12, 13, 14 | G4 | `/api/inventory` typed and consumed; opening-inventory setup and review flow; three distinct inventory figures labelled. |
| **G7 Frontend transaction + apply** | 15, 16 | G4 | Produced read-only and absent from the create payload; Save disabled on oversell; additive apply copy; already-applied state explained. |
| **G8 Frontend forecast chart (R1)** | 21 | G5 + G6 | Applied Production series renders; production-only product shows a chart, not the "no history" message; tooltips branch by point type; `tsc -b`, eslint and `npm run build` clean. |
| **G9 Guardrails** | 22 | G2 + G4 | Manual allocation create/update/delete changes no ledger row and no stock figure; one call site for `save_production_application`. |
| **G10 End-to-end** | 17 | G7 + G8 | Playwright specs green, network-stubbed. |
| **G11 Dev rollout** | 18 | every group above | `pg_dump` taken; explicit in-the-moment approval recorded; three migrations applied to `armando_furniture`; the full acceptance-criteria checklist walked and its results reported. |

**Parallelism:** G5 needs only G3 (and Task 4), so it can run alongside G4. G6/G7 need G4. G8 needs
both G5 and G6. G9 can run any time after G4. G11 is strictly last.

**Standing rules at every checkpoint**

1. `cd backend && python -m pytest -q` is green against `armando_furniture_test` — paste the tail.
2. The four forecast test files are **unedited**; `git diff --stat` proves it.
3. `git status` shows no changes outside the files that group's tasks name, and the five
   pre-existing untracked directories (`.qoder/`, `backend/scripts/`, `backups/`, `docs/`,
   `frontend/design-reference/`) are intact.
4. No migration has run against `armando_furniture` before G11.
5. **[VOID — AMENDMENT D]** No commit exists, and none may be created. Each task's Commit step is a prepared message only, reported to the user. Review packages are working-tree diffs. Every commit, push, deploy, and dev-DB migration needs the user's separate explicit approval.

---

# Self-review notes

**Spec coverage.** Every numbered requirement and every follow-up bullet maps to at least one task:
Req 1 → Tasks 6 (test) + existing behaviour; Req 2 → Task 10; Req 3 → Tasks 9, 10, 11; Req 4 →
Tasks 3, 4, 6; Req 5 → Tasks 8, 9; the three-way distinction → Tasks 9, 14; keep
`ProductionAllocation` → Task 6 (explicit test); ledger → Tasks 3, 4; resource items → Tasks 3, 5,
6; opening inventory → Tasks 1, 2, 13; nullable `production_cycle_id` → Task 8; derived stock →
Task 9; ledger authoritative → Tasks 4, 6; no stock-as-produced / no forecast inflation → Task 10 +
Deliverable 5; forecast compatibility → Deliverable 5; reject oversell incl. updates → Tasks 10, 11;
concurrency → Deliverable 6; duplicate applications → Tasks 3, 6, 16; preserve unsold across cycles
→ Tasks 4, 9; review gate → Tasks 2, 10, 13; reject unmatched dates → Task 8; test-DB prerequisite →
Task 0.

**R1 spec coverage.** Ledger as the authoritative production source → Tasks 19, 20; production
visible with no sale → Tasks 19, 20, 21; multiple sales must not duplicate → Task 19; opening
inventory never produced → Task 19; previous-cycle production stays historical → Task 19; preserve
pre-rollout behaviour → Tasks 19 Step 7, 20 Step 7, 11 Step 5, and the frozen four forecast test
files; `quantity_produced` retained for compatibility → Deliverable 5 ("What `quantity_produced`
is now") with Task 10 unchanged; manual allocation CRUD creates no inventory → Task 22 and
Deliverable 9; updated dependencies and checkpoints → Deliverables 3 & 4 and Deliverable 9.

**Known soft spots, called out rather than hidden.**
- Tasks 13, 14, 15 and 17 describe some component bodies and the Playwright stub fixture
  structurally (exact headers, exact asserted copy, exact props, exact scenarios) rather than as
  complete JSX/TS. Each one's *contract* is pinned by a test with literal assertions, and the
  surrounding code is named precisely (`ApplyConfirmModal.tsx` as the structural model,
  `UtilizationTable.tsx` for the table, `ResourcesPage.test.tsx` for the test wrapper). An executor
  must read those named files first.
- Task 2's `computed_field`-vs-explicit-field note for `created_by_username` is a genuine
  Pydantic-v2 uncertainty I could not resolve without running it; the step says which assertion
  decides it.
- Task 6 Step 6 depends on Task 7 Step 3 for the `consumption_override` keyword. The dependency is
  stated in both tasks with instructions for either execution order.

**Type consistency.** `find_resource_capacity_shortages`'s new parameter is
`already_consumed_by_resource_id` everywhere (Tasks 5, 6). `calculate_resource_utilization`'s is
`consumption_override` everywhere (Tasks 6, 7). `save_production_application`'s payloads are
`produced_by_product_id: dict[int, Decimal]` and `consumed_resources: list[dict]` with keys
`resource_id`/`resource_name`/`unit`/`consumed_quantity` in Tasks 4 and 6. The inventory query key
is `['inventory']` in Tasks 12, 13, 14, 15, 16. Status strings are `DRAFT`/`REVIEWED`/`SUPERSEDED`
throughout.

# Week Reference Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a student pick one of the 8 weeks from the official `weekly data references.xlsx` workbook, optionally edit a resource quantity, run the actual ILP solver against it, and see the computed allocation/profit next to the Excel's reference values — without ever touching live Product Data Management data.

**Architecture:** A static, versioned reference dataset (extracted once from the workbook, never re-read from it at runtime) plus a fixed, isolated historical product catalog feed the real `solve_optimization()` through a small new service, exposed by one new router, surfaced by one new frontend page. No new database table, no ORM involvement on the solver path — the comparison is pure, read-only computation.

**Tech Stack:** FastAPI + Pydantic (backend), existing `solve_optimization()` (unmodified), React + TypeScript (frontend), pytest + TestClient.

**Spec:** No separate spec document — the full requirement set is the user's own numbered list in this conversation turn (points 1–10 plus the "IMPORTANT DATA LIMITATION" note), reproduced in Global Constraints below. The completeness report delivered alongside this plan (workbook contents, per-week resource/allocation/profit tables, and the all-8-weeks reproduction proof) is the evidence base this plan argues from.

## Global Constraints

- Read the actual workbook; never invent or alter its values (requirement 1).
- Extract all 8 weeks of resources (2), allocations (3), and profit per week/product (4), preserving the workbook's own units and product names (5).
- Store the reference data separately from live Product Data Management records (6) — never write Excel values into `products`/`resources`/`product_resource_requirements`/`cycle_resources`.
- Exact-reference mode: load that week's verified historical configuration, run the actual solver, compare against the Excel (7).
- Modified-input mode: keep the week's historical configuration, substitute the student's resource value, run the actual solver, label the result as a modified-input run, not an exact match (8).
- Never hardcode expected quantities as solver output (9) — the solver never sees the Excel's expected allocation; comparison happens only after solving.
- Never block Generate because inputs differ from the Excel reference (10).
- BOM/product costs/minimum demand are **not** assumed identical across weeks without evidence — confirmed identical by direct re-solve (see completeness report); no per-week catalog variation is modeled, because none exists.
- Local/dev and isolated test database only; no production DB changes; no live product/resource edits; no migrations; no commit/push without separate approval.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/data/week_reference_catalog.py` | The one fixed, 11-product historical catalog (prices, labor costs, minimum demand, full BOM) as plain Python objects — isolated from `app.database.models`, never touches a DB session. |
| `backend/app/data/week_references.json` | The 8-week dataset extracted verbatim from the workbook: resource availability/consumed, expected allocation, expected profit per product and per week. |
| `backend/app/services/week_reference.py` | Loads both files above, builds in-memory solver inputs, applies optional per-resource overrides, calls the real `solve_optimization()`, compares against the Excel reference, returns a structured result. No DB parameter. |
| `backend/app/schemas/week_reference.py` | Pydantic request/response models for the new endpoints. |
| `backend/app/routers/week_reference.py` | `GET /api/week-references` (list all 8 weeks' reference tables) and `POST /api/week-references/{week}/compare` (run the solver, optionally with overrides). |
| `backend/main.py` | Register the new router (one import + one `include_router` line). |
| `backend/tests/test_week_reference.py` | Service-level tests: all 8 weeks reproduce exactly; one modified resource changes the result and is flagged; a mismatching input is never blocked. |
| `frontend/src/pages/week-reference-verification/api/weekReferenceApi.ts` | Thin fetch wrappers for the two endpoints. |
| `frontend/src/pages/week-reference-verification/api/weekReferenceTypes.ts` | TypeScript types mirroring the backend schemas. |
| `frontend/src/pages/week-reference-verification/hooks/useWeekReferenceVerification.ts` | Week selection, resource-override state, triggers compare, holds the result. |
| `frontend/src/pages/week-reference-verification/components/ReferenceResourceTable.tsx` | Editable table of the selected week's reference resources. |
| `frontend/src/pages/week-reference-verification/components/ComparisonResultTable.tsx` | Computed vs. reference allocation/profit, with the exact-match / modified-input badge. |
| `frontend/src/pages/week-reference-verification/WeekReferenceVerificationPage.tsx` | Page composition. |
| `frontend/src/app/router.tsx` | Add the new route. |
| `frontend/src/layouts/sidebar/Sidebar.tsx` | Add the new nav entry. |

---

### Task 1: Static reference dataset + fixed historical catalog

**Files:**
- Create: `backend/app/data/__init__.py` (empty)
- Create: `backend/app/data/week_reference_catalog.py`
- Create: `backend/app/data/week_references.json`
- Test: `backend/tests/test_week_reference_catalog.py`

**Interfaces:**
- Produces: `week_reference_catalog.CATALOG_PRODUCTS: list[CatalogProduct]`, `week_reference_catalog.CATALOG_RESOURCES: dict[str, CatalogResource]`, `week_reference_catalog.CATALOG_REQUIREMENTS: list[tuple[CatalogRequirement, CatalogResource]]` (same shape `solve_optimization()` already expects: a list of `(requirement, resource)` tuples, where `requirement` has `.product_id`, `.resource_id`, `.quantity_required`, and `resource` has `.id`, `.name`, `.unit`, `.resource_type`, `.is_active`). `CatalogProduct` has `.id`, `.name`, `.selling_price`, `.labor_cost`, `.minimum_demand`.
- Produces: `week_references.json` top-level shape:
  ```json
  {
    "resource_order": ["wood", "sandpaper", "nails", "wood_glue", "epoxy", "labor", "laborers", "circular_saw", "hand_planer", "table_planer", "doorknob"],
    "resource_names": {"wood": "Wood", "sandpaper": "Sandpaper", "nails": "Nails", "wood_glue": "Wood Glue", "epoxy": "Epoxy", "labor": "Labor", "laborers": "Laborers", "circular_saw": "Circular Saw", "hand_planer": "Hand Planer", "table_planer": "Table Planer", "doorknob": "Doorknob & Hinge"},
    "resource_units": {"wood": "bf", "sandpaper": "pcs", "nails": "kg", "wood_glue": "L", "epoxy": "L", "labor": "hrs", "laborers": "persons", "circular_saw": "hrs", "hand_planer": "hrs", "table_planer": "hrs", "doorknob": "set"},
    "product_order": ["dining_table_4", "dining_table_6", "dining_table_8", "ordinary_table", "bed_frame", "door_60", "door_70", "door_80", "door_90", "high_chair", "ordinary_chair"],
    "product_names": {"dining_table_4": "Dining table (4 seater)", "...": "..."},
    "weeks": {
      "1": {
        "resources": {"wood": {"available": 1000.0, "consumed": 821.0}, "laborers": {"available": 10.0, "consumed": null}, "...": {}},
        "allocation": {"dining_table_4": 1, "...": 10},
        "unit_profit": {"dining_table_4": 6764.5264, "...": 2302.12352},
        "total_profit": 102236.8148
      },
      "2": { "...": "..." }
    }
  }
  ```
- Consumes (Task 2): both of the above, by import/`json.load`.

- [ ] **Step 1: Write the failing catalog test**

```python
# backend/tests/test_week_reference_catalog.py
from decimal import Decimal

from app.data.week_reference_catalog import (
    CATALOG_PRODUCTS,
    CATALOG_REQUIREMENTS,
    CATALOG_RESOURCES,
)


def test_catalog_has_eleven_products():
    assert len(CATALOG_PRODUCTS) == 11
    assert {p.name for p in CATALOG_PRODUCTS} == {
        "Dining table (4 seater)", "Dining table (6 seater)",
        "Dining table (8 seater)", "Ordinary table", "Bed frame",
        "Door (60x210)", "Door (70x210)", "Door (80x210)",
        "Door (90x210)", "High chair", "Ordinary chair",
    }


def test_bedframe_wood_glue_requirement_is_historical_value():
    bed_frame_id = next(
        p.id for p in CATALOG_PRODUCTS if p.name == "Bed frame"
    )
    wood_glue_id = CATALOG_RESOURCES["wood_glue"].id

    requirement = next(
        requirement
        for requirement, resource in CATALOG_REQUIREMENTS
        if requirement.product_id == bed_frame_id
        and resource.id == wood_glue_id
    )

    assert requirement.quantity_required == Decimal("0.3000")


def test_door_products_use_the_verified_two_hour_hand_planer_value():
    hand_planer_id = CATALOG_RESOURCES["hand_planer"].id
    door_ids = {
        p.id for p in CATALOG_PRODUCTS if p.name.startswith("Door (")
    }

    for requirement, resource in CATALOG_REQUIREMENTS:
        if requirement.product_id in door_ids and resource.id == hand_planer_id:
            assert requirement.quantity_required == Decimal("2.0000")
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `python -m pytest tests/test_week_reference_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.data'`

- [ ] **Step 3: Write the catalog module**

```python
# backend/app/data/week_reference_catalog.py
"""
The one fixed, historical 11-product catalog behind every Week
Reference Verification comparison - verified in the Week 1-8
reconstruction investigation to reproduce the "weekly data
references.xlsx" workbook's allocation and profit exactly (within
~P0.3 of Excel's own rounding) for all 8 weeks when combined with
that week's own resource availability and NO forecast ceiling.

Deliberately independent of app.database.models: this catalog is
never read from or written to the live products/resources/
product_resource_requirements tables (Product Data Management owns
those) - it exists only to feed the real solve_optimization().

The Hand Planer requirement on the four doors/High Chair/Ordinary
Chair (2.0000, not 3.0000) and Bed Frame's Wood Glue requirement
(0.3000, not the live catalog's approved-current 1.3000) are the
historically-verified values, not necessarily what Product Data
Management shows today - see the Week 1-8 reconstruction
investigation for how each was confirmed.
"""
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class CatalogResource:
    id: int
    name: str
    unit: str
    resource_type: str
    is_active: bool = True


@dataclass
class CatalogProduct:
    id: int
    name: str
    selling_price: Decimal
    labor_cost: Decimal
    minimum_demand: Decimal
    is_active: bool = True


@dataclass
class CatalogRequirement:
    product_id: int
    resource_id: int
    quantity_required: Decimal


CATALOG_RESOURCES: dict[str, CatalogResource] = {
    "wood": CatalogResource(1, "Wood", "bf", "material"),
    "sandpaper": CatalogResource(2, "Sandpaper", "pcs", "material"),
    "nails": CatalogResource(3, "Nails", "kg", "material"),
    "wood_glue": CatalogResource(4, "Wood Glue", "L", "material"),
    "epoxy": CatalogResource(5, "Epoxy", "L", "material"),
    "labor": CatalogResource(6, "Labor", "hrs", "labor"),
    "circular_saw": CatalogResource(7, "Circular Saw", "hrs", "machine"),
    "hand_planer": CatalogResource(8, "Hand Planer", "hrs", "machine"),
    "table_planer": CatalogResource(9, "Table Planer", "hrs", "machine"),
    "doorknob": CatalogResource(10, "Doorknob & Hinge", "set", "material"),
}

# Unit prices never varied across any of the 8 weeks in the workbook.
CATALOG_RESOURCE_UNIT_PRICES: dict[str, Decimal] = {
    "wood": Decimal("84.00"), "epoxy": Decimal("690.00"),
    "nails": Decimal("54.00"), "wood_glue": Decimal("79.00"),
    "labor": Decimal("0.00"), "circular_saw": Decimal("31.57"),
    "sandpaper": Decimal("10.00"), "table_planer": Decimal("31.57"),
    "hand_planer": Decimal("15.78"), "doorknob": Decimal("300.00"),
}

CATALOG_PRODUCTS: list[CatalogProduct] = [
    CatalogProduct(1, "Dining table (4 seater)", Decimal("18000.00"), Decimal("5500.00"), Decimal("1")),
    CatalogProduct(2, "Dining table (6 seater)", Decimal("28000.00"), Decimal("7000.00"), Decimal("1")),
    CatalogProduct(3, "Dining table (8 seater)", Decimal("38000.00"), Decimal("10000.00"), Decimal("0")),
    CatalogProduct(4, "Ordinary table", Decimal("7000.00"), Decimal("1200.00"), Decimal("3")),
    CatalogProduct(5, "Bed frame", Decimal("15000.00"), Decimal("1500.00"), Decimal("2")),
    CatalogProduct(6, "Door (60x210)", Decimal("3800.00"), Decimal("500.00"), Decimal("5")),
    CatalogProduct(7, "Door (70x210)", Decimal("3800.00"), Decimal("500.00"), Decimal("5")),
    CatalogProduct(8, "Door (80x210)", Decimal("3800.00"), Decimal("500.00"), Decimal("4")),
    CatalogProduct(9, "Door (90x210)", Decimal("3800.00"), Decimal("500.00"), Decimal("4")),
    CatalogProduct(10, "High chair", Decimal("3500.00"), Decimal("350.00"), Decimal("2")),
    CatalogProduct(11, "Ordinary chair", Decimal("3500.00"), Decimal("300.00"), Decimal("3")),
]

_BOM: dict[int, dict[str, str]] = {
    1: {"wood": "50.0000", "epoxy": "0.6000", "nails": "0.5000", "wood_glue": "0.6000", "circular_saw": "15.0000", "sandpaper": "10.0000", "table_planer": "10.0000", "hand_planer": "10.0000", "labor": "40.0000"},
    2: {"wood": "75.0000", "epoxy": "1.0000", "nails": "0.5000", "wood_glue": "1.0000", "circular_saw": "20.0000", "sandpaper": "16.0000", "table_planer": "15.0000", "hand_planer": "15.0000", "labor": "60.0000"},
    3: {"wood": "100.0000", "epoxy": "1.5000", "nails": "1.0000", "wood_glue": "1.5000", "circular_saw": "30.0000", "sandpaper": "22.0000", "table_planer": "20.0000", "hand_planer": "20.0000", "labor": "80.0000"},
    4: {"wood": "15.0000", "epoxy": "0.2000", "nails": "0.2000", "wood_glue": "0.2000", "circular_saw": "2.0000", "sandpaper": "2.0000", "table_planer": "2.0000", "hand_planer": "2.0000", "labor": "10.0000"},
    5: {"wood": "30.0000", "epoxy": "0.2000", "nails": "0.4000", "wood_glue": "0.3000", "circular_saw": "10.0000", "sandpaper": "4.0000", "table_planer": "10.0000", "hand_planer": "10.0000", "labor": "40.0000"},
    6: {"wood": "25.0000", "epoxy": "0.2000", "nails": "0.2000", "wood_glue": "0.2000", "circular_saw": "2.0000", "sandpaper": "3.0000", "table_planer": "1.0000", "hand_planer": "2.0000", "doorknob": "1.0000", "labor": "8.0000"},
    7: {"wood": "25.0000", "epoxy": "0.2000", "nails": "0.2000", "wood_glue": "0.2000", "circular_saw": "2.0000", "sandpaper": "3.0000", "table_planer": "1.0000", "hand_planer": "2.0000", "doorknob": "1.0000", "labor": "8.0000"},
    8: {"wood": "25.0000", "epoxy": "0.2000", "nails": "0.2000", "wood_glue": "0.2000", "circular_saw": "2.0000", "sandpaper": "3.0000", "table_planer": "1.0000", "hand_planer": "2.0000", "doorknob": "1.0000", "labor": "8.0000"},
    9: {"wood": "25.0000", "epoxy": "0.2000", "nails": "0.2000", "wood_glue": "0.2000", "circular_saw": "2.0000", "sandpaper": "3.0000", "table_planer": "1.0000", "hand_planer": "2.0000", "doorknob": "1.0000", "labor": "8.0000"},
    10: {"wood": "8.0000", "epoxy": "0.1000", "nails": "0.0500", "wood_glue": "0.1000", "circular_saw": "2.0000", "sandpaper": "2.0000", "table_planer": "1.0000", "hand_planer": "2.0000", "labor": "8.0000"},
    11: {"wood": "8.0000", "epoxy": "0.1000", "nails": "0.0500", "wood_glue": "0.1000", "circular_saw": "2.0000", "sandpaper": "2.0000", "table_planer": "1.0000", "hand_planer": "2.0000", "labor": "8.0000"},
}

CATALOG_REQUIREMENTS: list[tuple[CatalogRequirement, CatalogResource]] = [
    (
        CatalogRequirement(product_id, CATALOG_RESOURCES[resource_key].id, Decimal(quantity)),
        CATALOG_RESOURCES[resource_key],
    )
    for product_id, bom in _BOM.items()
    for resource_key, quantity in bom.items()
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_week_reference_catalog.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Write `week_references.json`**

Populate every one of the 8 weeks' `resources`/`allocation`/`unit_profit`/`total_profit` blocks, using the exact values already extracted from the workbook in this investigation (see the completeness report delivered alongside this plan for the full per-week tables: resource availability/consumed, product allocation, and profit). Do not invent or round any value beyond what the workbook itself stores. `product_order` values are `["dining_table_4", "dining_table_6", "dining_table_8", "ordinary_table", "bed_frame", "door_60", "door_70", "door_80", "door_90", "high_chair", "ordinary_chair"]`, matching `CATALOG_PRODUCTS` order 1-11 above.

- [ ] **Step 6: Add a round-trip test for the JSON file**

```python
# append to backend/tests/test_week_reference_catalog.py
import json
from pathlib import Path


def test_week_references_json_has_all_eight_weeks():
    path = Path(__file__).resolve().parents[1] / "app" / "data" / "week_references.json"
    data = json.loads(path.read_text())

    assert set(data["weeks"].keys()) == {str(n) for n in range(1, 9)}

    week_one = data["weeks"]["1"]
    assert week_one["resources"]["wood"]["available"] == 1000.0
    assert week_one["resources"]["wood"]["consumed"] == 821.0
    assert week_one["allocation"]["ordinary_chair"] == 10
    assert week_one["total_profit"] == 102236.8148
```

- [ ] **Step 7: Run test to verify it passes**

Run: `python -m pytest tests/test_week_reference_catalog.py -v`
Expected: PASS (4 passed)

- [ ] **Step 8: Commit**

```bash
git add backend/app/data backend/tests/test_week_reference_catalog.py
git commit -m "feat: add Week 1-8 reference dataset and isolated historical catalog"
```

---

### Task 2: Week reference comparison service

**Files:**
- Create: `backend/app/services/week_reference.py`
- Test: `backend/tests/test_week_reference.py`

**Interfaces:**
- Consumes: `CATALOG_PRODUCTS`, `CATALOG_REQUIREMENTS`, `CATALOG_RESOURCES`, `CATALOG_RESOURCE_UNIT_PRICES` from Task 1; `app.services.optimization.solve_optimization` (existing, unmodified).
- Produces: `list_week_reference_summaries() -> list[dict]` and `compare_week_reference(week: int, resource_overrides: dict[str, Decimal] | None) -> dict` with return shape:
  ```python
  {
      "week": 1,
      "is_modified_input": False,
      "resources_used": {"wood": Decimal("1000.0000"), "...": Decimal("...")},
      "status": "Optimal",
      "computed_allocation": {"dining_table_4": 1, "...": 10},
      "reference_allocation": {"dining_table_4": 1, "...": 10},
      "allocation_matches_reference": True,
      "computed_total": 40,
      "reference_total": 40,
      "computed_profit": Decimal("102237.1600"),
      "reference_profit": Decimal("102236.8148"),
  }
  ```
  (Task 4's router returns this dict almost as-is through a Pydantic response model.)

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_week_reference.py
from decimal import Decimal

import pytest

from app.services.week_reference import (
    compare_week_reference,
    list_week_reference_summaries,
)


def test_lists_all_eight_weeks():
    summaries = list_week_reference_summaries()

    assert [s["week"] for s in summaries] == list(range(1, 9))
    assert summaries[0]["resources"]["wood"]["available"] == Decimal("1000.0000")


@pytest.mark.parametrize("week", list(range(1, 9)))
def test_exact_reference_resources_reproduce_the_excel_allocation_and_profit(week):
    """
    No expected quantity is ever passed INTO the solver here - this
    only compares the solver's own output against the Excel reference
    AFTER solving, per requirement 9 ("never hardcode expected
    quantities as solver output").
    """
    result = compare_week_reference(week, resource_overrides=None)

    assert result["status"] == "Optimal"
    assert result["is_modified_input"] is False
    assert result["computed_allocation"] == result["reference_allocation"]
    assert result["computed_total"] == result["reference_total"]
    # Same ~P0.3-0.4 Excel-side rounding margin established for every
    # week in the Week 1-8 reconstruction investigation - not an exact
    # equality, because the Excel's own total is itself rounded.
    assert abs(result["computed_profit"] - result["reference_profit"]) <= Decimal("0.50")


def test_modifying_one_resource_is_flagged_and_still_solves():
    result = compare_week_reference(
        week=1,
        resource_overrides={"wood_glue": Decimal("1.3000")},
    )

    assert result["status"] == "Optimal"
    assert result["is_modified_input"] is True
    assert result["resources_used"]["wood_glue"] == Decimal("1.3000")
    # Other weeks'/resources' values are untouched - only the one
    # overridden resource changes from the week's historical figure.
    assert result["resources_used"]["wood"] == Decimal("1000.0000")


def test_a_resource_change_that_breaks_the_reference_match_is_never_blocked():
    """
    Requirement 10: Generate must never be blocked just because the
    result differs from the Excel reference.
    """
    result = compare_week_reference(
        week=1,
        resource_overrides={"doorknob": Decimal("0.0000")},
    )

    assert result["status"] == "Optimal"
    assert result["allocation_matches_reference"] is False
    assert result["computed_allocation"] != result["reference_allocation"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_week_reference.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.week_reference'`

- [ ] **Step 3: Write the service**

```python
# backend/app/services/week_reference.py
"""
Pure, read-only comparison between the actual ILP solver and the
official "weekly data references.xlsx" workbook (Week 1-8). Never
touches a database session, never writes to products/resources/
cycle_resources, and never feeds an expected quantity into the
solver - only compares its output afterward.
"""
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from app.data.week_reference_catalog import (
    CATALOG_PRODUCTS,
    CATALOG_REQUIREMENTS,
    CATALOG_RESOURCES,
    CATALOG_RESOURCE_UNIT_PRICES,
)
from app.services.optimization import solve_optimization

_REFERENCE_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "week_references.json"
)


@dataclass
class _CycleResourceInput:
    id: int
    resource_id: int
    available_quantity: Decimal
    unit_price: Decimal
    resource: object


def _load_reference_data() -> dict:
    return json.loads(_REFERENCE_PATH.read_text())


def _resource_keys_with_solver_rows() -> list[str]:
    # "laborers" has an availability figure in the workbook but is not
    # one of CATALOG_RESOURCES - it was never a solver-constrained
    # resource (see the Week 1-8 reconstruction investigation), so it
    # is reported to the caller but never turned into a CycleResource.
    return [
        key for key in _load_reference_data()["resource_order"]
        if key in CATALOG_RESOURCES
    ]


def list_week_reference_summaries() -> list[dict]:
    data = _load_reference_data()
    summaries = []

    for week_str, week_data in sorted(
        data["weeks"].items(), key=lambda item: int(item[0])
    ):
        resources = {
            key: {
                "available": Decimal(str(week_data["resources"][key]["available"])),
                "consumed": (
                    Decimal(str(week_data["resources"][key]["consumed"]))
                    if week_data["resources"][key]["consumed"] is not None
                    else None
                ),
                "unit": data["resource_units"][key],
                "name": data["resource_names"][key],
            }
            for key in data["resource_order"]
        }

        summaries.append({
            "week": int(week_str),
            "resources": resources,
            "reference_total": sum(week_data["allocation"].values()),
            "reference_profit": Decimal(str(week_data["total_profit"])),
        })

    return summaries


def compare_week_reference(
    week: int,
    resource_overrides: dict[str, Decimal] | None = None,
) -> dict:
    data = _load_reference_data()
    week_data = data["weeks"][str(week)]
    overrides = resource_overrides or {}

    resources_used: dict[str, Decimal] = {}
    cycle_resources = []

    for index, key in enumerate(_resource_keys_with_solver_rows()):
        historical_value = Decimal(str(week_data["resources"][key]["available"]))
        value = overrides.get(key, historical_value)
        resources_used[key] = value

        catalog_resource = CATALOG_RESOURCES[key]
        cycle_resources.append(
            _CycleResourceInput(
                id=index,
                resource_id=catalog_resource.id,
                available_quantity=value,
                unit_price=CATALOG_RESOURCE_UNIT_PRICES[key],
                resource=catalog_resource,
            )
        )

    is_modified_input = any(
        key in overrides
        and overrides[key] != Decimal(str(week_data["resources"][key]["available"]))
        for key in overrides
    )

    result = solve_optimization(
        cycle_id=week,
        products=CATALOG_PRODUCTS,
        cycle_resources=cycle_resources,
        requirements=CATALOG_REQUIREMENTS,
        forecast=None,
    )

    product_key_by_id = {
        catalog_product.id: key
        for key, catalog_product in zip(
            data["product_order"], CATALOG_PRODUCTS
        )
    }

    computed_allocation = {
        product_key_by_id[allocation["product_id"]]: allocation["quantity"]
        for allocation in result["allocations"]
    }
    reference_allocation = {
        key: int(value) for key, value in week_data["allocation"].items()
    }

    return {
        "week": week,
        "is_modified_input": is_modified_input,
        "resources_used": resources_used,
        "status": result["status"],
        "computed_allocation": computed_allocation,
        "reference_allocation": reference_allocation,
        "allocation_matches_reference": (
            computed_allocation == reference_allocation
        ),
        "computed_total": sum(computed_allocation.values()),
        "reference_total": sum(reference_allocation.values()),
        "computed_profit": Decimal(str(result["objective_value"])),
        "reference_profit": Decimal(str(week_data["total_profit"])),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_week_reference.py -v`
Expected: PASS (11 passed: 1 list test + 8 parametrized exact-match tests + 2 override tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/week_reference.py backend/tests/test_week_reference.py
git commit -m "feat: add Week 1-8 reference comparison service"
```

---

### Task 3: Pydantic schemas

**Files:**
- Create: `backend/app/schemas/week_reference.py`
- Test: `backend/tests/test_week_reference_schemas.py`

**Interfaces:**
- Consumes: dict shapes produced by Task 2's `list_week_reference_summaries()`/`compare_week_reference()`.
- Produces: `WeekReferenceSummaryResponse`, `WeekReferenceCompareRequest`, `WeekReferenceCompareResponse` for Task 4's router to use as `response_model=...` / request body type.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_week_reference_schemas.py
from decimal import Decimal

from app.schemas.week_reference import (
    WeekReferenceCompareRequest,
    WeekReferenceCompareResponse,
)


def test_compare_request_accepts_optional_overrides():
    request = WeekReferenceCompareRequest(
        resource_overrides={"wood_glue": Decimal("1.3")}
    )

    assert request.resource_overrides == {"wood_glue": Decimal("1.3")}


def test_compare_request_defaults_to_no_overrides():
    request = WeekReferenceCompareRequest()

    assert request.resource_overrides is None


def test_compare_response_round_trips_service_output():
    response = WeekReferenceCompareResponse(
        week=1,
        is_modified_input=False,
        resources_used={"wood": Decimal("1000.0000")},
        status="Optimal",
        computed_allocation={"dining_table_4": 1},
        reference_allocation={"dining_table_4": 1},
        allocation_matches_reference=True,
        computed_total=1,
        reference_total=1,
        computed_profit=Decimal("102237.1600"),
        reference_profit=Decimal("102236.8148"),
    )

    assert response.week == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_week_reference_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.week_reference'`

- [ ] **Step 3: Write the schemas**

```python
# backend/app/schemas/week_reference.py
from decimal import Decimal

from pydantic import BaseModel


class WeekReferenceResourceSummary(BaseModel):
    available: Decimal
    consumed: Decimal | None
    unit: str
    name: str


class WeekReferenceSummaryResponse(BaseModel):
    week: int
    resources: dict[str, WeekReferenceResourceSummary]
    reference_total: int
    reference_profit: Decimal


class WeekReferenceCompareRequest(BaseModel):
    resource_overrides: dict[str, Decimal] | None = None


class WeekReferenceCompareResponse(BaseModel):
    week: int
    is_modified_input: bool
    resources_used: dict[str, Decimal]
    status: str
    computed_allocation: dict[str, int]
    reference_allocation: dict[str, int]
    allocation_matches_reference: bool
    computed_total: int
    reference_total: int
    computed_profit: Decimal
    reference_profit: Decimal
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_week_reference_schemas.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/week_reference.py backend/tests/test_week_reference_schemas.py
git commit -m "feat: add Week 1-8 reference comparison schemas"
```

---

### Task 4: Router + registration

**Files:**
- Create: `backend/app/routers/week_reference.py`
- Modify: `backend/main.py` (add import + `include_router` line, following the existing pattern at `main.py:10-23` and `:62-75`)
- Test: `backend/tests/test_week_reference_router.py`

**Interfaces:**
- Consumes: `list_week_reference_summaries`, `compare_week_reference` (Task 2); `WeekReferenceSummaryResponse`, `WeekReferenceCompareRequest`, `WeekReferenceCompareResponse` (Task 3).
- Produces: `GET /api/week-references`, `POST /api/week-references/{week}/compare` for the frontend (Task 5) to call.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_week_reference_router.py
def test_list_week_references(client):
    response = client.get("/api/week-references")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 8
    assert body[0]["week"] == 1


def test_compare_week_one_exact_reference(client):
    response = client.post("/api/week-references/1/compare", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Optimal"
    assert body["is_modified_input"] is False
    assert body["computed_allocation"] == body["reference_allocation"]


def test_compare_with_resource_override_is_flagged_and_not_blocked(client):
    response = client.post(
        "/api/week-references/1/compare",
        json={"resource_overrides": {"doorknob": "0"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_modified_input"] is True
    assert body["status"] == "Optimal"


def test_compare_unknown_week_returns_404(client):
    response = client.post("/api/week-references/99/compare", json={})

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_week_reference_router.py -v`
Expected: FAIL with 404 "Not Found" on every route (router not registered yet).

- [ ] **Step 3: Write the router**

```python
# backend/app/routers/week_reference.py
from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.week_reference import (
    WeekReferenceCompareRequest,
    WeekReferenceCompareResponse,
    WeekReferenceSummaryResponse,
)
from app.services.auth import get_current_user
from app.services.week_reference import (
    compare_week_reference,
    list_week_reference_summaries,
)

router = APIRouter(
    prefix="/api/week-references",
    tags=["Week Reference Verification"],
    dependencies=[Depends(get_current_user)],
)

_VALID_WEEKS = range(1, 9)


@router.get(
    "",
    response_model=list[WeekReferenceSummaryResponse],
    summary="List the 8 official reference weeks",
)
def list_week_references():
    return list_week_reference_summaries()


@router.post(
    "/{week}/compare",
    response_model=WeekReferenceCompareResponse,
    summary="Run the actual solver against a reference week, optionally with resource overrides",
)
def compare_week(
    week: int,
    request: WeekReferenceCompareRequest,
):
    if week not in _VALID_WEEKS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reference week not found (valid range: 1-8)",
        )

    return compare_week_reference(week, request.resource_overrides)
```

- [ ] **Step 4: Register the router**

Add to `backend/main.py` after line 23 (alongside the other router imports):

```python
from app.routers.week_reference import router as week_reference_router
```

Add after line 75 (alongside the other `include_router` calls):

```python
app.include_router(week_reference_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_week_reference_router.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Run the full backend test suite to confirm no regression**

Run: `python -m pytest -q` (from `backend/`, against `armando_furniture_test` per `conftest.py`'s database guard)
Expected: all pre-existing tests still pass, plus every test added in Tasks 1-4.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/week_reference.py backend/main.py backend/tests/test_week_reference_router.py
git commit -m "feat: expose Week 1-8 reference comparison API"
```

---

### Task 5: Frontend API layer

**Files:**
- Create: `frontend/src/pages/week-reference-verification/api/weekReferenceTypes.ts`
- Create: `frontend/src/pages/week-reference-verification/api/weekReferenceApi.ts`
- Test: `frontend/src/pages/week-reference-verification/api/weekReferenceApi.test.ts`

**Interfaces:**
- Consumes: the JSON shapes Task 4's endpoints return.
- Produces: `WeekReferenceSummary`, `WeekReferenceCompareResult` types; `listWeekReferences(): Promise<WeekReferenceSummary[]>`, `compareWeekReference(week: number, resourceOverrides?: Record<string, number>): Promise<WeekReferenceCompareResult>` for Task 6's hook to call.

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/pages/week-reference-verification/api/weekReferenceApi.test.ts
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { compareWeekReference, listWeekReferences } from './weekReferenceApi'

describe('weekReferenceApi', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('lists week references', async () => {
    const mockResponse = [{ week: 1, resources: {}, reference_total: 40, reference_profit: '102236.8148' }]
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    } as Response)

    const result = await listWeekReferences()

    expect(fetch).toHaveBeenCalledWith('/api/week-references', expect.any(Object))
    expect(result).toEqual(mockResponse)
  })

  it('compares a week with resource overrides', async () => {
    const mockResponse = { week: 1, is_modified_input: true, status: 'Optimal' }
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    } as Response)

    const result = await compareWeekReference(1, { doorknob: 0 })

    expect(fetch).toHaveBeenCalledWith(
      '/api/week-references/1/compare',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ resource_overrides: { doorknob: 0 } }),
      }),
    )
    expect(result).toEqual(mockResponse)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npm test -- weekReferenceApi.test.ts`
Expected: FAIL — module `./weekReferenceApi` does not exist.

- [ ] **Step 3: Write the types and API module**

```typescript
// frontend/src/pages/week-reference-verification/api/weekReferenceTypes.ts
export interface WeekReferenceResourceSummary {
  available: string
  consumed: string | null
  unit: string
  name: string
}

export interface WeekReferenceSummary {
  week: number
  resources: Record<string, WeekReferenceResourceSummary>
  reference_total: number
  reference_profit: string
}

export interface WeekReferenceCompareResult {
  week: number
  is_modified_input: boolean
  resources_used: Record<string, string>
  status: string
  computed_allocation: Record<string, number>
  reference_allocation: Record<string, number>
  allocation_matches_reference: boolean
  computed_total: number
  reference_total: number
  computed_profit: string
  reference_profit: string
}
```

```typescript
// frontend/src/pages/week-reference-verification/api/weekReferenceApi.ts
import type {
  WeekReferenceCompareResult,
  WeekReferenceSummary,
} from './weekReferenceTypes'

export async function listWeekReferences(): Promise<WeekReferenceSummary[]> {
  const response = await fetch('/api/week-references', { method: 'GET' })

  if (!response.ok) {
    throw new Error('Failed to load week references')
  }

  return response.json()
}

export async function compareWeekReference(
  week: number,
  resourceOverrides?: Record<string, number>,
): Promise<WeekReferenceCompareResult> {
  const response = await fetch(`/api/week-references/${week}/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resource_overrides: resourceOverrides ?? null }),
  })

  if (!response.ok) {
    throw new Error('Failed to compare week reference')
  }

  return response.json()
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- weekReferenceApi.test.ts`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/week-reference-verification/api
git commit -m "feat: add Week 1-8 reference comparison API client"
```

---

### Task 6: Frontend page (hook, components, route, nav)

**Files:**
- Create: `frontend/src/pages/week-reference-verification/hooks/useWeekReferenceVerification.ts`
- Create: `frontend/src/pages/week-reference-verification/components/ReferenceResourceTable.tsx`
- Create: `frontend/src/pages/week-reference-verification/components/ComparisonResultTable.tsx`
- Create: `frontend/src/pages/week-reference-verification/WeekReferenceVerificationPage.tsx`
- Test: `frontend/src/pages/week-reference-verification/hooks/useWeekReferenceVerification.test.tsx`
- Modify: `frontend/src/app/router.tsx` (add route, following the pattern at lines 19/79-82)
- Modify: `frontend/src/layouts/sidebar/Sidebar.tsx` (add nav entry, following the pattern at lines 39-56)

**Interfaces:**
- Consumes: `listWeekReferences`, `compareWeekReference`, `WeekReferenceSummary`, `WeekReferenceCompareResult` (Task 5).
- Produces: `WeekReferenceVerificationPage` default export, mounted at `/week-reference-verification`.

- [ ] **Step 1: Write the failing hook test**

```typescript
// frontend/src/pages/week-reference-verification/hooks/useWeekReferenceVerification.test.tsx
import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import * as api from '../api/weekReferenceApi'
import { useWeekReferenceVerification } from './useWeekReferenceVerification'

describe('useWeekReferenceVerification', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(api, 'listWeekReferences').mockResolvedValue([
      { week: 1, resources: {}, reference_total: 40, reference_profit: '102236.8148' },
    ])
  })

  it('loads the week list on mount and selects week 1 by default', async () => {
    const { result } = renderHook(() => useWeekReferenceVerification())

    await waitFor(() => expect(result.current.weeks).toHaveLength(1))
    expect(result.current.selectedWeek).toBe(1)
  })

  it('runs the comparison and marks it modified when a resource override is set', async () => {
    vi.spyOn(api, 'compareWeekReference').mockResolvedValue({
      week: 1,
      is_modified_input: true,
      resources_used: {},
      status: 'Optimal',
      computed_allocation: {},
      reference_allocation: {},
      allocation_matches_reference: false,
      computed_total: 0,
      reference_total: 40,
      computed_profit: '0',
      reference_profit: '102236.8148',
    })

    const { result } = renderHook(() => useWeekReferenceVerification())
    await waitFor(() => expect(result.current.weeks).toHaveLength(1))

    act(() => {
      result.current.setResourceOverride('doorknob', 0)
    })

    await act(async () => {
      await result.current.runComparison()
    })

    expect(result.current.result?.is_modified_input).toBe(true)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- useWeekReferenceVerification.test.tsx`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Write the hook**

```typescript
// frontend/src/pages/week-reference-verification/hooks/useWeekReferenceVerification.ts
import { useCallback, useEffect, useState } from 'react'
import {
  compareWeekReference,
  listWeekReferences,
} from '../api/weekReferenceApi'
import type {
  WeekReferenceCompareResult,
  WeekReferenceSummary,
} from '../api/weekReferenceTypes'

export function useWeekReferenceVerification() {
  const [weeks, setWeeks] = useState<WeekReferenceSummary[]>([])
  const [selectedWeek, setSelectedWeek] = useState<number>(1)
  const [resourceOverrides, setResourceOverrides] = useState<Record<string, number>>({})
  const [result, setResult] = useState<WeekReferenceCompareResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    listWeekReferences().then((loaded) => {
      setWeeks(loaded)
      if (loaded.length > 0) {
        setSelectedWeek(loaded[0].week)
      }
    })
  }, [])

  const selectWeek = useCallback((week: number) => {
    setSelectedWeek(week)
    setResourceOverrides({})
    setResult(null)
  }, [])

  const setResourceOverride = useCallback((resourceKey: string, value: number) => {
    setResourceOverrides((previous) => ({ ...previous, [resourceKey]: value }))
  }, [])

  const runComparison = useCallback(async () => {
    setIsLoading(true)
    try {
      const overrides = Object.keys(resourceOverrides).length > 0 ? resourceOverrides : undefined
      const comparison = await compareWeekReference(selectedWeek, overrides)
      setResult(comparison)
    } finally {
      setIsLoading(false)
    }
  }, [selectedWeek, resourceOverrides])

  return {
    weeks,
    selectedWeek,
    selectWeek,
    resourceOverrides,
    setResourceOverride,
    result,
    isLoading,
    runComparison,
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- useWeekReferenceVerification.test.tsx`
Expected: PASS (2 passed)

- [ ] **Step 5: Write the display components**

```typescript
// frontend/src/pages/week-reference-verification/components/ReferenceResourceTable.tsx
import type { WeekReferenceSummary } from '../api/weekReferenceTypes'

interface ReferenceResourceTableProps {
  week: WeekReferenceSummary
  overrides: Record<string, number>
  onOverrideChange: (resourceKey: string, value: number) => void
}

export function ReferenceResourceTable({
  week,
  overrides,
  onOverrideChange,
}: ReferenceResourceTableProps) {
  return (
    <table>
      <thead>
        <tr>
          <th>Resource</th>
          <th>Reference quantity</th>
          <th>Unit</th>
          <th>Your value</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(week.resources).map(([key, resource]) => (
          <tr key={key}>
            <td>{resource.name}</td>
            <td>{resource.available}</td>
            <td>{resource.unit}</td>
            <td>
              <input
                type="number"
                step="0.0001"
                value={overrides[key] ?? Number(resource.available)}
                onChange={(event) => onOverrideChange(key, Number(event.target.value))}
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
```

```typescript
// frontend/src/pages/week-reference-verification/components/ComparisonResultTable.tsx
import type { WeekReferenceCompareResult } from '../api/weekReferenceTypes'

interface ComparisonResultTableProps {
  result: WeekReferenceCompareResult
}

export function ComparisonResultTable({ result }: ComparisonResultTableProps) {
  const productKeys = Object.keys(result.reference_allocation)

  return (
    <div>
      <p>
        {result.is_modified_input
          ? 'Modified-input run — not an exact reference match'
          : result.allocation_matches_reference
            ? 'Exact reference match'
            : 'Reference resources, but allocation differs'}
      </p>

      <table>
        <thead>
          <tr>
            <th>Product</th>
            <th>Computed</th>
            <th>Reference</th>
          </tr>
        </thead>
        <tbody>
          {productKeys.map((key) => (
            <tr key={key}>
              <td>{key}</td>
              <td>{result.computed_allocation[key] ?? 0}</td>
              <td>{result.reference_allocation[key] ?? 0}</td>
            </tr>
          ))}
          <tr>
            <td>Total</td>
            <td>{result.computed_total}</td>
            <td>{result.reference_total}</td>
          </tr>
          <tr>
            <td>Profit</td>
            <td>{result.computed_profit}</td>
            <td>{result.reference_profit}</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
```

```typescript
// frontend/src/pages/week-reference-verification/WeekReferenceVerificationPage.tsx
import { ComparisonResultTable } from './components/ComparisonResultTable'
import { ReferenceResourceTable } from './components/ReferenceResourceTable'
import { useWeekReferenceVerification } from './hooks/useWeekReferenceVerification'

export default function WeekReferenceVerificationPage() {
  const {
    weeks,
    selectedWeek,
    selectWeek,
    resourceOverrides,
    setResourceOverride,
    result,
    isLoading,
    runComparison,
  } = useWeekReferenceVerification()

  const currentWeek = weeks.find((week) => week.week === selectedWeek)

  return (
    <div>
      <h1>Week Reference Verification</h1>

      <select
        value={selectedWeek}
        onChange={(event) => selectWeek(Number(event.target.value))}
      >
        {weeks.map((week) => (
          <option key={week.week} value={week.week}>
            Week {week.week}
          </option>
        ))}
      </select>

      {currentWeek && (
        <ReferenceResourceTable
          week={currentWeek}
          overrides={resourceOverrides}
          onOverrideChange={setResourceOverride}
        />
      )}

      <button
        type="button"
        onClick={() => void runComparison()}
        disabled={isLoading}
      >
        Run against solver
      </button>

      {result && <ComparisonResultTable result={result} />}
    </div>
  )
}
```

- [ ] **Step 6: Register the route**

Add to `frontend/src/app/router.tsx`, after the other page imports (around line 26):

```typescript
import WeekReferenceVerificationPage from '../pages/week-reference-verification/WeekReferenceVerificationPage'
```

Add inside the protected `<Route element={<AppLayout />}>` block, after the `/inventory` route (around line 109):

```tsx
<Route
  path="/week-reference-verification"
  element={<WeekReferenceVerificationPage />}
/>
```

- [ ] **Step 7: Add the sidebar nav entry**

Add to `frontend/src/layouts/sidebar/Sidebar.tsx`, following the existing entry shape (e.g. after the Demand Forecasting entry around line 81):

```typescript
{
  label: 'Week Reference Verification',
  icon: FileCheck,
  path: '/week-reference-verification',
},
```

(Import `FileCheck` from `lucide-react` alongside the sidebar's other icon imports if not already present.)

- [ ] **Step 8: Manually verify in the browser**

Run the dev server, log in, navigate to `/week-reference-verification`, select each of Weeks 1-8, click "Run against solver" with no changes (confirm "Exact reference match" for all 8), then change one resource value and confirm the "Modified-input run" label appears and Generate is not blocked.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/pages/week-reference-verification frontend/src/app/router.tsx frontend/src/layouts/sidebar/Sidebar.tsx
git commit -m "feat: add Week Reference Verification page"
```

---

## Self-Review

**Spec coverage:**
1. Read the actual workbook, never invent values → Task 1 Step 5 (data transcribed verbatim from the completeness report, itself read via `openpyxl`). ✅
2. Extract all 8 weeks of resources → Task 1 (`week_references.json`). ✅
3. Extract all 8 weeks of allocations → Task 1. ✅
4. Extract profit per week and per product → Task 1 (`unit_profit`, `total_profit`). ✅
5. Preserve units/names → Task 1 (`resource_names`, `resource_units`, `product_names` verbatim from the workbook). ✅
6. Store separately from Product Data Management → Task 1 (`app/data/`, never touches `products`/`resources` tables). ✅
7. Exact-reference flow (load historical config, solve, compare) → Task 2 `compare_week_reference` with no overrides. ✅
8. Modified-input flow (keep historical config, swap resource, solve, flag) → Task 2's `is_modified_input` + `resource_overrides`. ✅
9. Never hardcode expected quantities as solver output → Task 2 calls `solve_optimization()` with no knowledge of `reference_allocation`; comparison happens only after. ✅
10. Never block Generate on mismatch → Task 2's `test_a_resource_change_that_breaks_the_reference_match_is_never_blocked` / Task 4's equivalent router test. ✅
Data limitation note (don't assume identical weekly configs) → addressed by the completeness report's full 8-week reproduction proof, referenced in Task 1's catalog module docstring. ✅

**Placeholder scan:** none found — every step has real code or an explicit extraction instruction naming the exact source (completeness report).

**Type consistency:** `resource_overrides: dict[str, Decimal] | None` (Task 2/3/4) ↔ `resourceOverrides?: Record<string, number>` (Task 5/6) — consistent across the boundary; `compare_week_reference`/`compareWeekReference` and `list_week_reference_summaries`/`listWeekReferences` naming matches on both sides of each task boundary.

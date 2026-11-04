"""
Regression test: the original Week 1 production plan (production_cycle_id
1 in the development/production database) must remain reproducible from
its true historical inputs, using the real solve_optimization()
implementation, unmodified.

This fixture exists because a live investigation (see the repository's
own history and the "reconstruct Week 1" task) found that the
development database's current state for cycle 1 no longer reflects the
inputs that actually produced the historical result:

  - Products 1-11 (the original catalog) were deactivated on 2026-10-08
    in favor of duplicate active products 12-23, some with edited labor
    costs (e.g. Bed Frame's and Dining Table 6-seater's labor_cost were
    zeroed on the new rows).
  - cycle_resources for cycle 1 were edited on 2026-10-23 (Epoxy, Nails,
    Wood Glue, Sandpaper availability all changed away from their
    original Week 1 values).
  - The deactivated products' own BOM also drifted: seed.py raised the
    Hand Planer requirement on the four doors, High Chair, and Ordinary
    Chair from 2 to 3 on 2026-09-13 (commit a57b2b2), a month after the
    historical run - the *currently active* duplicate products (12-23)
    still carry the correct original value of 2 for those same six
    items, which is how the drift was caught and corrected here.

Every other value below (resource availability/unit prices, product
selling prices/labor costs/minimum demand, every other BOM line) is
copied verbatim from data that is STILL recoverable read-only from the
live database:
  - Resource availability for Week 1: resource_utilization_history_items
    for utilization_run_id=79 (generated 2026-08-16, before any of the
    later edits), which independently matches the task's reference
    "Available Quantity" AND "Consumed Quantity" tables exactly.
  - Resource unit prices, product prices/labor costs/minimum demand, and
    the rest of the BOM: the still-intact (though deactivated) products
    1-11 and their product_resource_requirements rows, which match
    backend/app/database/seed.py's own "authoritative client BOM"
    verbatim except for the one Hand Planer value above.

The Hand Planer correction (2, not the currently-stored 3) was verified,
not assumed: using 2 reconciles ALL TEN resource consumption figures in
the historical record to the exact decimal (Wood 821, Epoxy 8, Nails
7.2, Wood Glue 8.2, Labor 480, Circular Saw 127, Sandpaper 124, Table
Planer 87, Hand Planer 117, Doorknob & Hinge 18), and reconciles total
profit to within P0.35 of the recorded historical figure (see the
dedicated profit test below for why that P0.35 remains).

No expected quantity is ever fed into the solver's inputs below - the
11 figures under test exist only as assertions, never as a constraint,
BOM value, price, or bound.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from app.database.models import (
    CycleResource,
    Product,
    ProductionCycle,
    ProductResourceRequirement,
    Resource,
)
from app.services.optimization import (
    get_optimization_data,
    solve_optimization,
)
from conftest import purge_ledger


# Historical Week 1 total_profit, as recorded in optimization_runs for
# the real cycle (id 164, is_summary_only=true - an aggregate figure
# imported from the student's Excel/thesis sheet, per migration
# c7a1e4d9f2b8 and commit 9103983, never computed by this codebase).
_HISTORICAL_RECORDED_TOTAL_PROFIT = Decimal("102236.81")

# Expected Week 1 allocation (task reference table) - assertions only,
# never used to build any fixture input below.
_EXPECTED_QUANTITIES_BY_NAME = {
    "Week1 Dining Table (4 seater)": 1,
    "Week1 Dining Table (6 seater)": 1,
    "Week1 Dining Table (8 seater)": 0,
    "Week1 Ordinary Table": 6,
    "Week1 Bed Frame": 2,
    "Week1 Door (60x210)": 5,
    "Week1 Door (70x210)": 5,
    "Week1 Door (80x210)": 4,
    "Week1 Door (90x210)": 4,
    "Week1 High Chair": 2,
    "Week1 Ordinary Chair": 10,
}


@pytest.fixture
def week1_historical_scenario(db):
    """
    Builds an isolated copy of the Week 1 scenario in the dedicated test
    database (armando_furniture_test - see conftest.py's database guard),
    never the development/production database. Every resource and
    product name is prefixed "Week1 " so this fixture can never collide
    with another fixture's rows, and the whole scenario is torn down
    unconditionally in `finally`.
    """

    resource_specs = [
        ("Week1 Wood", "material", "board ft", "1000.0000", "84.00"),
        ("Week1 Epoxy", "material", "liter", "8.0000", "690.00"),
        ("Week1 Nails", "material", "kg", "8.0000", "54.00"),
        ("Week1 Wood Glue", "material", "liter", "9.0000", "79.00"),
        ("Week1 Labor", "labor", "hours", "480.0000", "0.00"),
        ("Week1 Circular Saw", "machine", "hrs", "336.0000", "31.57"),
        ("Week1 Sandpaper", "material", "pcs", "130.0000", "10.00"),
        ("Week1 Table Planer", "machine", "hrs", "96.0000", "31.57"),
        ("Week1 Hand Planer", "machine", "hrs", "240.0000", "15.78"),
        ("Week1 Doorknob & Hinge", "material", "set", "25.0000", "300.00"),
    ]

    resources = {
        name: Resource(
            name=name,
            resource_type=resource_type,
            unit=unit,
            is_active=True,
        )
        for name, resource_type, unit, _avail, _price in resource_specs
    }
    db.add_all(resources.values())
    db.commit()

    for resource in resources.values():
        db.refresh(resource)

    product_specs = [
        ("Week1 Dining Table (4 seater)", "18000.00", "5500.00", "1"),
        ("Week1 Dining Table (6 seater)", "28000.00", "7000.00", "1"),
        ("Week1 Dining Table (8 seater)", "38000.00", "10000.00", "0"),
        ("Week1 Ordinary Table", "7000.00", "1200.00", "3"),
        ("Week1 Bed Frame", "15000.00", "1500.00", "2"),
        ("Week1 Door (60x210)", "3800.00", "500.00", "5"),
        ("Week1 Door (70x210)", "3800.00", "500.00", "5"),
        ("Week1 Door (80x210)", "3800.00", "500.00", "4"),
        ("Week1 Door (90x210)", "3800.00", "500.00", "4"),
        ("Week1 High Chair", "3500.00", "350.00", "2"),
        ("Week1 Ordinary Chair", "3500.00", "300.00", "3"),
    ]

    products = {
        name: Product(
            name=name,
            selling_price=Decimal(selling_price),
            labor_cost=Decimal(labor_cost),
            minimum_demand=Decimal(minimum_demand),
            is_active=True,
        )
        for name, selling_price, labor_cost, minimum_demand in product_specs
    }
    db.add_all(products.values())
    db.commit()

    for product in products.values():
        db.refresh(product)

    cycle = ProductionCycle(
        cycle_date=datetime(2026, 8, 16),
        start_date=datetime(2026, 8, 16),
        end_date=datetime(2026, 8, 23),
        status="OPEN",
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    cycle_resources = [
        CycleResource(
            production_cycle_id=cycle.id,
            resource_id=resources[name].id,
            available_quantity=Decimal(available_quantity),
            unit_price=Decimal(unit_price),
        )
        for name, _type, _unit, available_quantity, unit_price in resource_specs
    ]
    db.add_all(cycle_resources)
    db.commit()

    # BOM for every product except Labor hours (added separately below).
    # The Hand Planer entries on the four doors, High Chair and Ordinary
    # Chair are 2.0000 - the verified-correct historical value - never
    # the 3.0000 currently stored against the real (deactivated)
    # products 1-11 in the development database. See module docstring.
    bom = {
        "Week1 Dining Table (4 seater)": {
            "Week1 Wood": "50.0000", "Week1 Epoxy": "0.6000",
            "Week1 Nails": "0.5000", "Week1 Wood Glue": "0.6000",
            "Week1 Circular Saw": "15.0000", "Week1 Sandpaper": "10.0000",
            "Week1 Table Planer": "10.0000", "Week1 Hand Planer": "10.0000",
        },
        "Week1 Dining Table (6 seater)": {
            "Week1 Wood": "75.0000", "Week1 Epoxy": "1.0000",
            "Week1 Nails": "0.5000", "Week1 Wood Glue": "1.0000",
            "Week1 Circular Saw": "20.0000", "Week1 Sandpaper": "16.0000",
            "Week1 Table Planer": "15.0000", "Week1 Hand Planer": "15.0000",
        },
        "Week1 Dining Table (8 seater)": {
            "Week1 Wood": "100.0000", "Week1 Epoxy": "1.5000",
            "Week1 Nails": "1.0000", "Week1 Wood Glue": "1.5000",
            "Week1 Circular Saw": "30.0000", "Week1 Sandpaper": "22.0000",
            "Week1 Table Planer": "20.0000", "Week1 Hand Planer": "20.0000",
        },
        "Week1 Ordinary Table": {
            "Week1 Wood": "15.0000", "Week1 Epoxy": "0.2000",
            "Week1 Nails": "0.2000", "Week1 Wood Glue": "0.2000",
            "Week1 Circular Saw": "2.0000", "Week1 Sandpaper": "2.0000",
            "Week1 Table Planer": "2.0000", "Week1 Hand Planer": "2.0000",
        },
        "Week1 Bed Frame": {
            "Week1 Wood": "30.0000", "Week1 Epoxy": "0.2000",
            "Week1 Nails": "0.4000", "Week1 Wood Glue": "0.3000",
            "Week1 Circular Saw": "10.0000", "Week1 Sandpaper": "4.0000",
            "Week1 Table Planer": "10.0000", "Week1 Hand Planer": "10.0000",
        },
        "Week1 Door (60x210)": {
            "Week1 Wood": "25.0000", "Week1 Epoxy": "0.2000",
            "Week1 Nails": "0.2000", "Week1 Wood Glue": "0.2000",
            "Week1 Circular Saw": "2.0000", "Week1 Sandpaper": "3.0000",
            "Week1 Table Planer": "1.0000", "Week1 Hand Planer": "2.0000",
            "Week1 Doorknob & Hinge": "1.0000",
        },
        "Week1 Door (70x210)": {
            "Week1 Wood": "25.0000", "Week1 Epoxy": "0.2000",
            "Week1 Nails": "0.2000", "Week1 Wood Glue": "0.2000",
            "Week1 Circular Saw": "2.0000", "Week1 Sandpaper": "3.0000",
            "Week1 Table Planer": "1.0000", "Week1 Hand Planer": "2.0000",
            "Week1 Doorknob & Hinge": "1.0000",
        },
        "Week1 Door (80x210)": {
            "Week1 Wood": "25.0000", "Week1 Epoxy": "0.2000",
            "Week1 Nails": "0.2000", "Week1 Wood Glue": "0.2000",
            "Week1 Circular Saw": "2.0000", "Week1 Sandpaper": "3.0000",
            "Week1 Table Planer": "1.0000", "Week1 Hand Planer": "2.0000",
            "Week1 Doorknob & Hinge": "1.0000",
        },
        "Week1 Door (90x210)": {
            "Week1 Wood": "25.0000", "Week1 Epoxy": "0.2000",
            "Week1 Nails": "0.2000", "Week1 Wood Glue": "0.2000",
            "Week1 Circular Saw": "2.0000", "Week1 Sandpaper": "3.0000",
            "Week1 Table Planer": "1.0000", "Week1 Hand Planer": "2.0000",
            "Week1 Doorknob & Hinge": "1.0000",
        },
        "Week1 High Chair": {
            "Week1 Wood": "8.0000", "Week1 Epoxy": "0.1000",
            "Week1 Nails": "0.0500", "Week1 Wood Glue": "0.1000",
            "Week1 Circular Saw": "2.0000", "Week1 Sandpaper": "2.0000",
            "Week1 Table Planer": "1.0000", "Week1 Hand Planer": "2.0000",
        },
        "Week1 Ordinary Chair": {
            "Week1 Wood": "8.0000", "Week1 Epoxy": "0.1000",
            "Week1 Nails": "0.0500", "Week1 Wood Glue": "0.1000",
            "Week1 Circular Saw": "2.0000", "Week1 Sandpaper": "2.0000",
            "Week1 Table Planer": "1.0000", "Week1 Hand Planer": "2.0000",
        },
    }

    labor_hours = {
        "Week1 Dining Table (4 seater)": "40.0000",
        "Week1 Dining Table (6 seater)": "60.0000",
        "Week1 Dining Table (8 seater)": "80.0000",
        "Week1 Ordinary Table": "10.0000",
        "Week1 Bed Frame": "40.0000",
        "Week1 Door (60x210)": "8.0000",
        "Week1 Door (70x210)": "8.0000",
        "Week1 Door (80x210)": "8.0000",
        "Week1 Door (90x210)": "8.0000",
        "Week1 High Chair": "8.0000",
        "Week1 Ordinary Chair": "8.0000",
    }

    requirements = []

    for product_name, resource_quantities in bom.items():
        for resource_name, quantity in resource_quantities.items():
            requirements.append(
                ProductResourceRequirement(
                    product_id=products[product_name].id,
                    resource_id=resources[resource_name].id,
                    quantity_required=Decimal(quantity),
                )
            )

        requirements.append(
            ProductResourceRequirement(
                product_id=products[product_name].id,
                resource_id=resources["Week1 Labor"].id,
                quantity_required=Decimal(labor_hours[product_name]),
            )
        )

    db.add_all(requirements)
    db.commit()

    product_ids = [product.id for product in products.values()]
    resource_ids = [resource.id for resource in resources.values()]

    try:
        yield {
            "cycle": cycle,
            "products": products,
            "resources": resources,
        }

    finally:
        purge_ledger(db, cycle_ids=[cycle.id], product_ids=product_ids)

        db.query(ProductResourceRequirement).filter(
            ProductResourceRequirement.product_id.in_(product_ids)
        ).delete(synchronize_session=False)

        db.query(CycleResource).filter(
            CycleResource.production_cycle_id == cycle.id
        ).delete(synchronize_session=False)

        db.delete(cycle)

        for product in products.values():
            db.delete(product)

        for resource in resources.values():
            db.delete(resource)

        db.commit()


def _solve(db, cycle_id):
    """
    Loads data through the real get_optimization_data() and solves
    through the real solve_optimization() - no mocking of either, and
    no forecast ceiling passed: Week 1 predates any sales_transactions
    in the historical record (the earliest forecast_runs row postdates
    it by 12 days), so the original run had no forecast constraint
    either.
    """

    data = get_optimization_data(db, cycle_id)

    return solve_optimization(
        cycle_id,
        data["products"],
        data["cycle_resources"],
        data["requirements"],
    )


def _quantities_by_name(result, products_by_name):
    id_to_name = {
        product.id: name for name, product in products_by_name.items()
    }

    return {
        id_to_name[allocation["product_id"]]: allocation["quantity"]
        for allocation in result["allocations"]
        if allocation["product_id"] in id_to_name
    }


def test_week1_reproduces_the_exact_historical_allocation(
    db, week1_historical_scenario,
):
    """
    Core requirement: solving the real, reconstructed Week 1 inputs
    through the unmodified optimizer must return exactly the historical
    11-product allocation - not merely the same total of 40 units.
    """

    cycle = week1_historical_scenario["cycle"]
    products_by_name = week1_historical_scenario["products"]

    result = _solve(db, cycle.id)

    assert result["status"] == "Optimal"

    quantities = _quantities_by_name(result, products_by_name)

    for name, expected_quantity in _EXPECTED_QUANTITIES_BY_NAME.items():
        assert quantities[name] == expected_quantity, (
            f"{name}: expected {expected_quantity}, got {quantities[name]}"
        )

    assert sum(quantities.values()) == 40


def test_week1_is_deterministic_across_repeated_solves(
    db, week1_historical_scenario,
):
    """
    Repeated solves against the identical, unchanged Week 1 inputs must
    return identical results every time - the same determinism guarantee
    test_optimization_determinism.py establishes for Generate in general,
    checked here specifically against the historical scenario.
    """

    cycle = week1_historical_scenario["cycle"]

    first = _solve(db, cycle.id)

    for _ in range(5):
        repeat = _solve(db, cycle.id)

        assert repeat["status"] == "Optimal"
        assert repeat["allocations"] == first["allocations"]
        assert repeat["objective_value"] == first["objective_value"]


def test_week1_total_profit_matches_historical_record_within_rounding(
    db, week1_historical_scenario,
):
    """
    The reconstructed scenario's profit must land within a few centavos
    of the historical record (optimization_runs.id=164 in the real
    database, total_profit=102236.81) - not exactly equal, because that
    recorded figure is itself an aggregate value imported from the
    student's Excel/thesis sheet (is_summary_only=true, zero rows in
    optimization_results - see migration c7a1e4d9f2b8 and commit
    9103983), never computed by this codebase at the time. The P0.35
    (0.0003%) gap is consistent with ordinary spreadsheet rounding, not
    with any remaining input mismatch: every one of the 10 resource
    consumption figures in the historical record (Wood 821, Epoxy 8,
    Nails 7.2, Wood Glue 8.2, Labor 480, Circular Saw 127, Sandpaper
    124, Table Planer 87, Hand Planer 117, Doorknob & Hinge 18)
    reconciles to the exact decimal against this fixture's BOM at the
    expected allocation.
    """

    cycle = week1_historical_scenario["cycle"]

    result = _solve(db, cycle.id)

    reproduced_total_profit = Decimal(str(result["objective_value"]))
    difference = abs(
        reproduced_total_profit - _HISTORICAL_RECORDED_TOTAL_PROFIT
    )

    assert difference <= Decimal("0.50"), (
        f"reproduced total profit {reproduced_total_profit} drifted "
        f"from the historical record "
        f"{_HISTORICAL_RECORDED_TOTAL_PROFIT} by more than rounding "
        f"noise ({difference})"
    )

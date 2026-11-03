"""
Regression tests for the approved determinism fix: repeated Generate
calls with identical inputs must return identical product quantities,
even when more than one allocation shares the same maximum profit.

Uses a dedicated, minimal two-product/one-resource scenario
engineered to have a genuine profit tie, rather than the shared
test_products/test_resources fixtures (whose baseline optimum is
already unique and would not exercise the tie-break path at all).

Tie construction: "Det Bedframe" (lower product_id) requires 2 Nails
per unit and sells for a profit of 200; "Det Door" (higher product_id)
requires 1 Nail per unit and sells for a profit of 100 - exactly the
same profit-per-nail (100) for both, so any split of the 8 available
Nails that uses them in full (2*Bedframe + Door == 8) ties at the same
total profit of 800. Resource unit_price and product labor_cost are
both zero throughout, so each product's unit profit equals its
selling_price exactly - kept simple on purpose, to make the expected
tie (and its expected resolution) easy to verify by hand.
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
from conftest import purge_ledger


@pytest.fixture
def tied_profit_scenario(db):
    nails = Resource(
        name="Det Nails",
        resource_type="material",
        unit="kg",
        is_active=True,
    )
    db.add(nails)
    db.commit()
    db.refresh(nails)

    # Ascending by name here only for readability - the fixture's
    # product_id ordering is whatever the database assigns on
    # INSERT, same as any other product. Bedframe is created first so
    # it reliably has the LOWER id, matching the "ascending id"
    # tie-break rule under test.
    bedframe = Product(
        name="Det Bedframe",
        selling_price=Decimal("200.00"),
        labor_cost=Decimal("0.00"),
        is_active=True,
    )
    door = Product(
        name="Det Door",
        selling_price=Decimal("100.00"),
        labor_cost=Decimal("0.00"),
        is_active=True,
    )
    db.add_all([bedframe, door])
    db.commit()
    db.refresh(bedframe)
    db.refresh(door)

    assert bedframe.id < door.id, (
        "fixture assumes insertion order determines id order"
    )

    cycle = ProductionCycle(
        cycle_date=datetime(2026, 11, 1),
        start_date=datetime(2026, 11, 1),
        end_date=datetime(2026, 11, 1),
        status="PLANNED",
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    cycle_resource = CycleResource(
        production_cycle_id=cycle.id,
        resource_id=nails.id,
        available_quantity=Decimal("8.0000"),
        unit_price=Decimal("0.0000"),
    )
    db.add(cycle_resource)

    requirements = [
        ProductResourceRequirement(
            product_id=bedframe.id,
            resource_id=nails.id,
            quantity_required=Decimal("2.0000"),
        ),
        ProductResourceRequirement(
            product_id=door.id,
            resource_id=nails.id,
            quantity_required=Decimal("1.0000"),
        ),
    ]
    db.add_all(requirements)
    db.commit()

    try:
        yield {
            "cycle": cycle,
            "nails": nails,
            "bedframe": bedframe,
            "door": door,
            "cycle_resource": cycle_resource,
        }

    finally:
        purge_ledger(db, cycle_ids=[cycle.id])

        db.query(CycleResource).filter(
            CycleResource.production_cycle_id == cycle.id
        ).delete(synchronize_session=False)

        db.query(ProductResourceRequirement).filter(
            ProductResourceRequirement.product_id.in_(
                [bedframe.id, door.id]
            )
        ).delete(synchronize_session=False)

        db.delete(cycle)
        db.delete(bedframe)
        db.delete(door)
        db.delete(nails)
        db.commit()


def _optimize(client, cycle_id):
    response = client.post(
        f"/api/production-cycles/{cycle_id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )

    assert response.status_code == 200, response.text

    return response.json()


def _quantities_by_name(payload, names_by_id):
    return {
        names_by_id[item["product_id"]]: item["quantity"]
        for item in payload["allocations"]
        if item["product_id"] in names_by_id
    }


def test_repeated_generate_with_identical_inputs_is_deterministic(
    client, tied_profit_scenario,
):
    """
    Core business requirement: Generate called repeatedly with no
    change to any input must return the exact same quantities every
    time - not just the same total profit.
    """

    cycle = tied_profit_scenario["cycle"]

    first = _optimize(client, cycle.id)

    for _ in range(5):
        repeat = _optimize(client, cycle.id)
        assert repeat["allocations"] == first["allocations"]
        assert repeat["total_profit"] == first["total_profit"]


def test_tied_solutions_select_the_documented_lowest_id_tie_break(
    client, tied_profit_scenario,
):
    """
    Nails=8, Bedframe needs 2/unit, Door needs 1/unit, and both have
    the same profit-per-nail (100) - 2*Bedframe + Door = 8 ties at
    profit 800 for Bedframe in {0, 1, 2, 3, 4}. The documented rule
    (prefer the lowest product_id) must always resolve this to the
    single point that maximizes Bedframe's own quantity first:
    Bedframe=4, Door=0 - not any of the other four equally-profitable
    splits.
    """

    cycle = tied_profit_scenario["cycle"]
    names_by_id = {
        tied_profit_scenario["bedframe"].id: "Bedframe",
        tied_profit_scenario["door"].id: "Door",
    }

    payload = _optimize(client, cycle.id)
    quantities = _quantities_by_name(payload, names_by_id)

    assert quantities == {"Bedframe": 4, "Door": 0}


def test_tie_break_never_reduces_the_maximum_profit(
    client, tied_profit_scenario,
):
    cycle = tied_profit_scenario["cycle"]

    payload = _optimize(client, cycle.id)

    # 4 Bedframes * 200 profit = 800, the true maximum for 8 Nails at
    # 100 profit-per-nail either way the Nails are spent.
    assert Decimal(str(payload["total_profit"])) == Decimal("800.0000")

    total_profit = sum(
        Decimal(item["total_profit"])
        for item in payload["allocations"]
    )
    assert total_profit == Decimal("800.0000")


def test_different_inputs_still_produce_different_optimal_results(
    db, client, tied_profit_scenario,
):
    """
    The determinism fix must not freeze Generate onto one fixed
    answer regardless of input - raising Nails to 9 breaks the exact
    2:1 tie (2*4=8 uses all 8, but a 9th Nail can only ever fit
    another whole Door, never a fractional Bedframe), so the unique
    best use of the 9th Nail is one more Door.
    """

    cycle = tied_profit_scenario["cycle"]
    names_by_id = {
        tied_profit_scenario["bedframe"].id: "Bedframe",
        tied_profit_scenario["door"].id: "Door",
    }

    baseline = _quantities_by_name(
        _optimize(client, cycle.id), names_by_id,
    )
    assert baseline == {"Bedframe": 4, "Door": 0}

    cycle_resource = tied_profit_scenario["cycle_resource"]
    cycle_resource.available_quantity = Decimal("9.0000")
    db.commit()

    changed = _quantities_by_name(
        _optimize(client, cycle.id), names_by_id,
    )
    assert changed == {"Bedframe": 4, "Door": 1}
    assert changed != baseline


def test_previous_apply_does_not_affect_generate_results(
    client, tied_profit_scenario,
):
    """
    Requirement 9: a prior Apply must not change what a later Generate
    computes - the result must be deterministic (same as before the
    Apply) AND unaffected by however much the prior application
    consumed, consistent with the approved repeated-Apply business
    rule (optimize_production never passes already-consumed capacity
    into solve_optimization).
    """

    cycle = tied_profit_scenario["cycle"]
    names_by_id = {
        tied_profit_scenario["bedframe"].id: "Bedframe",
        tied_profit_scenario["door"].id: "Door",
    }

    before_apply = _quantities_by_name(
        _optimize(client, cycle.id), names_by_id,
    )
    assert before_apply == {"Bedframe": 4, "Door": 0}

    apply_response = client.post(
        f"/api/production-cycles/{cycle.id}/optimize/apply"
    )
    assert apply_response.status_code == 200, apply_response.text

    after_apply = _quantities_by_name(
        _optimize(client, cycle.id), names_by_id,
    )
    assert after_apply == before_apply


# --- Phase 2 (adaptive, minimum-demand-infeasible path) ----------------
#
# Scenario: "Det Tie A", "Det Tie B", "Det Tie C" each have
# minimum_demand=1. A and B both need 1 unit of "Det Tie Scarce"
# (available_quantity=1) and tie exactly on unit profit (100 each,
# zero resource/labor cost) - so the exact minimum vector (A=1, B=1,
# C=1) needs 2 Scarce against only 1 available, forcing the adaptive
# (Stage 1-5) path, and Stage 3 faces a genuine coverage tie between
# covering A or covering B (never both). C needs a separate,
# plentiful resource and is never part of the tie. The documented
# rule (ascending product_id) must always resolve the tie to
# whichever of A/B has the lower id.


@pytest.fixture
def adaptive_tie_scenario(db):
    scarce = Resource(
        name="Det Tie Scarce",
        resource_type="material",
        unit="kg",
        is_active=True,
    )
    plentiful = Resource(
        name="Det Tie Open",
        resource_type="material",
        unit="kg",
        is_active=True,
    )
    db.add_all([scarce, plentiful])
    db.commit()
    db.refresh(scarce)
    db.refresh(plentiful)

    # Created in this order so "a" reliably gets the lower id - the
    # one the tie-break rule is expected to favor.
    product_a = Product(
        name="Det Tie A",
        selling_price=Decimal("100.00"),
        labor_cost=Decimal("0.00"),
        is_active=True,
        minimum_demand=Decimal("1"),
    )
    product_b = Product(
        name="Det Tie B",
        selling_price=Decimal("100.00"),
        labor_cost=Decimal("0.00"),
        is_active=True,
        minimum_demand=Decimal("1"),
    )
    product_c = Product(
        name="Det Tie C",
        selling_price=Decimal("50.00"),
        labor_cost=Decimal("0.00"),
        is_active=True,
        minimum_demand=Decimal("1"),
    )
    db.add_all([product_a, product_b, product_c])
    db.commit()
    db.refresh(product_a)
    db.refresh(product_b)
    db.refresh(product_c)

    assert product_a.id < product_b.id, (
        "fixture assumes insertion order determines id order"
    )

    cycle = ProductionCycle(
        cycle_date=datetime(2026, 11, 2),
        start_date=datetime(2026, 11, 2),
        end_date=datetime(2026, 11, 2),
        status="PLANNED",
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    db.add_all([
        CycleResource(
            production_cycle_id=cycle.id,
            resource_id=scarce.id,
            available_quantity=Decimal("1.0000"),
            unit_price=Decimal("0.0000"),
        ),
        CycleResource(
            production_cycle_id=cycle.id,
            resource_id=plentiful.id,
            available_quantity=Decimal("50.0000"),
            unit_price=Decimal("0.0000"),
        ),
    ])

    requirements = [
        ProductResourceRequirement(
            product_id=product_a.id,
            resource_id=scarce.id,
            quantity_required=Decimal("1.0000"),
        ),
        ProductResourceRequirement(
            product_id=product_b.id,
            resource_id=scarce.id,
            quantity_required=Decimal("1.0000"),
        ),
        ProductResourceRequirement(
            product_id=product_c.id,
            resource_id=plentiful.id,
            quantity_required=Decimal("1.0000"),
        ),
    ]
    db.add_all(requirements)
    db.commit()

    product_ids = [product_a.id, product_b.id, product_c.id]

    try:
        yield {
            "cycle": cycle,
            "a": product_a,
            "b": product_b,
            "c": product_c,
        }

    finally:
        purge_ledger(db, cycle_ids=[cycle.id])

        db.query(CycleResource).filter(
            CycleResource.production_cycle_id == cycle.id
        ).delete(synchronize_session=False)

        db.query(ProductResourceRequirement).filter(
            ProductResourceRequirement.product_id.in_(product_ids)
        ).delete(synchronize_session=False)

        db.delete(cycle)
        db.delete(product_a)
        db.delete(product_b)
        db.delete(product_c)
        db.delete(scarce)
        db.delete(plentiful)
        db.commit()


def test_adaptive_path_repeated_generate_is_deterministic(
    client, adaptive_tie_scenario,
):
    """
    Core requirement, Phase 2: the minimum-demand vector here is
    infeasible (forces the five-stage adaptive path), and Stage 3
    faces a genuine coverage tie. Repeated Generate with no input
    change must still return the exact same quantities every time.
    """

    cycle = adaptive_tie_scenario["cycle"]

    first = _optimize(client, cycle.id)

    for _ in range(5):
        repeat = _optimize(client, cycle.id)
        assert repeat["allocations"] == first["allocations"]
        assert repeat["total_profit"] == first["total_profit"]


def test_adaptive_path_coverage_tie_selects_the_lower_id_product(
    client, adaptive_tie_scenario,
):
    """
    A and B tie exactly on unit profit and both compete for the same
    single unit of Det Tie Scarce - only one of them can ever be
    covered. The documented rule must always resolve this to A (the
    lower id): A reaches its minimum_demand of 1, B is left at 0.
    """

    cycle = adaptive_tie_scenario["cycle"]
    names_by_id = {
        adaptive_tie_scenario["a"].id: "A",
        adaptive_tie_scenario["b"].id: "B",
        adaptive_tie_scenario["c"].id: "C",
    }

    payload = _optimize(client, cycle.id)
    quantities = _quantities_by_name(payload, names_by_id)

    assert quantities["A"] == 1
    assert quantities["B"] == 0
    # C is never part of the tie - it has its own resource and is
    # free to be produced up to its own capacity (50).
    assert quantities["C"] == 50


def test_adaptive_path_tie_break_does_not_reduce_profit_or_coverage(
    client, adaptive_tie_scenario,
):
    """
    The deterministic choice (covering A, not B) must achieve the
    SAME total profit as covering B instead would have (100 each) -
    the tie-break must never leave the cycle worse off than the
    untouched Stage 1-4 floors already guaranteed.
    """

    cycle = adaptive_tie_scenario["cycle"]

    payload = _optimize(client, cycle.id)

    # 1 covered tie-winner (100 profit) + 50 units of C (50 * 50 = 2500).
    assert Decimal(str(payload["total_profit"])) == Decimal("2600.0000")


def test_adaptive_path_previous_apply_does_not_affect_generate_results(
    client, adaptive_tie_scenario,
):
    """
    Requirement 9, Phase 2: a prior Apply must not change what a
    later Generate computes on the adaptive path either.
    """

    cycle = adaptive_tie_scenario["cycle"]
    names_by_id = {
        adaptive_tie_scenario["a"].id: "A",
        adaptive_tie_scenario["b"].id: "B",
        adaptive_tie_scenario["c"].id: "C",
    }

    before_apply = _quantities_by_name(
        _optimize(client, cycle.id), names_by_id,
    )
    assert before_apply == {"A": 1, "B": 0, "C": 50}

    apply_response = client.post(
        f"/api/production-cycles/{cycle.id}/optimize/apply"
    )
    assert apply_response.status_code == 200, apply_response.text

    after_apply = _quantities_by_name(
        _optimize(client, cycle.id), names_by_id,
    )
    assert after_apply == before_apply

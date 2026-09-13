"""
Tests for the "Unknown" resource_usage entry fix in
app/services/optimization.py::calculate_optimized_resource_usage.

Root cause: that function iterates every CycleResource row for the
cycle and looks up its name/unit from a dict built ONLY from currently-
referenced ProductResourceRequirement rows - a CycleResource row whose
resource_id is no longer referenced by any requirement (superseded/
renamed resource after migration 7f3cba51324d's remap, or any other
orphaned/stray row) fell through to a fabricated "Unknown"/"" entry
with required_quantity 0. This is purely a reporting artifact: such a
row already contributes a mathematically trivial `0 <= available_
quantity` constraint in add_resource_constraints() regardless (see
that function - empty resource_requirements list -> zero consumption),
so it never affected the ILP's chosen quantities, revenue, cost, or
profit. The fix only skips it when building the resource_usage report;
nothing is deleted, nothing is written back to the database.
"""

from decimal import Decimal

from app.database.models import CycleResource, Resource
from app.services.optimization import (
    build_optimization_result,
    calculate_optimized_resource_usage,
    get_optimization_data,
    identify_optimization_bottlenecks,
    solve_optimization,
)


def _get_test_data(db, optimization_cycle):
    return get_optimization_data(db, optimization_cycle.id)


def _add_orphan_cycle_resource(db, optimization_cycle, name="Test Orphan Resource"):
    """
    Simulates the reported production symptom: a CycleResource row
    whose resource has NO current ProductResourceRequirement pointing
    at it (e.g. because it was superseded/renamed and requirements
    were remapped elsewhere, or it's simply a stray/unused row).
    """

    orphan_resource = Resource(
        name=name, resource_type="material", unit="pcs", is_active=True,
    )
    db.add(orphan_resource)
    db.commit()
    db.refresh(orphan_resource)

    orphan_cycle_resource = CycleResource(
        production_cycle_id=optimization_cycle.id,
        resource_id=orphan_resource.id,
        available_quantity=Decimal("50.0000"),
        unit_price=Decimal("5.00"),
    )
    db.add(orphan_cycle_resource)
    db.commit()
    db.refresh(orphan_cycle_resource)

    return orphan_resource, orphan_cycle_resource


def _cleanup_orphan(db, orphan_resource, orphan_cycle_resource):
    db.delete(orphan_cycle_resource)
    db.delete(orphan_resource)
    db.commit()


def test_orphan_cycle_resource_does_not_appear_as_unknown(
    db, optimization_cycle, test_resources,
):
    orphan_resource, orphan_cycle_resource = _add_orphan_cycle_resource(
        db, optimization_cycle,
    )

    try:
        data = _get_test_data(db, optimization_cycle)
        result = solve_optimization(
            optimization_cycle.id,
            data["products"],
            data["cycle_resources"],
            data["requirements"],
        )

        usage = calculate_optimized_resource_usage(
            result["allocations"],
            data["cycle_resources"],
            data["requirements"],
        )

        resource_ids_in_usage = {item["resource_id"] for item in usage}
        names_in_usage = {item["resource_name"] for item in usage}

        assert orphan_cycle_resource.resource_id not in resource_ids_in_usage
        assert "Unknown" not in names_in_usage
        assert "" not in {item["unit"] for item in usage}
    finally:
        _cleanup_orphan(db, orphan_resource, orphan_cycle_resource)


def test_active_canonical_resources_still_appear_with_correct_quantities(
    db, optimization_cycle, test_resources,
):
    orphan_resource, orphan_cycle_resource = _add_orphan_cycle_resource(
        db, optimization_cycle,
    )

    try:
        data = _get_test_data(db, optimization_cycle)
        result = solve_optimization(
            optimization_cycle.id,
            data["products"],
            data["cycle_resources"],
            data["requirements"],
        )

        usage = calculate_optimized_resource_usage(
            result["allocations"],
            data["cycle_resources"],
            data["requirements"],
        )

        # Same expected numbers as the pre-existing
        # test_optimized_resource_usage - proves the fix doesn't
        # change correct entries, only removes unresolvable ones.
        labor_resource = next(
            r for r in test_resources if r.name == "Test Labor"
        )
        labor = next(
            item for item in usage if item["resource_id"] == labor_resource.id
        )

        assert labor["resource_name"] == "Test Labor"
        assert labor["unit"] == "hours"
        assert labor["required_quantity"] == Decimal("576.0000")
        assert labor["available_quantity"] == Decimal("576.0000")
        assert labor["remaining_quantity"] == Decimal("0.0000")
    finally:
        _cleanup_orphan(db, orphan_resource, orphan_cycle_resource)


def test_bottlenecks_unaffected_by_orphan_row_filtering(
    db, optimization_cycle, test_resources,
):
    orphan_resource, orphan_cycle_resource = _add_orphan_cycle_resource(
        db, optimization_cycle,
    )

    try:
        data = _get_test_data(db, optimization_cycle)
        result = solve_optimization(
            optimization_cycle.id,
            data["products"],
            data["cycle_resources"],
            data["requirements"],
        )
        usage = calculate_optimized_resource_usage(
            result["allocations"], data["cycle_resources"], data["requirements"],
        )
        bottlenecks = identify_optimization_bottlenecks(usage)

        # Same single real bottleneck (Test Labor) as the pre-existing
        # test_optimization_bottleneck - the orphan row (available=50,
        # required=0, remaining=50) must not spuriously appear as a
        # second "bottleneck" or otherwise change this result.
        assert len(bottlenecks) == 1
        assert bottlenecks[0]["resource_name"] == "Test Labor"
    finally:
        _cleanup_orphan(db, orphan_resource, orphan_cycle_resource)


def test_orphan_cycle_resource_does_not_change_allocations_or_financials(
    db, optimization_cycle, test_products, test_resources,
):
    # Baseline: solve without the orphan row.
    data_before = _get_test_data(db, optimization_cycle)
    result_before = solve_optimization(
        optimization_cycle.id,
        data_before["products"],
        data_before["cycle_resources"],
        data_before["requirements"],
    )
    final_before = build_optimization_result(
        optimization_cycle.id,
        data_before["products"],
        data_before["cycle_resources"],
        data_before["requirements"],
        result_before["allocations"],
        result_before["status"],
    )

    orphan_resource, orphan_cycle_resource = _add_orphan_cycle_resource(
        db, optimization_cycle,
    )

    try:
        data_after = _get_test_data(db, optimization_cycle)
        result_after = solve_optimization(
            optimization_cycle.id,
            data_after["products"],
            data_after["cycle_resources"],
            data_after["requirements"],
        )
        final_after = build_optimization_result(
            optimization_cycle.id,
            data_after["products"],
            data_after["cycle_resources"],
            data_after["requirements"],
            result_after["allocations"],
            result_after["status"],
        )

        allocations_before = {
            a["product_id"]: a["quantity"] for a in final_before["allocations"]
        }
        allocations_after = {
            a["product_id"]: a["quantity"] for a in final_after["allocations"]
        }

        assert allocations_before == allocations_after
        assert final_before["total_revenue"] == final_after["total_revenue"]
        assert final_before["total_cost"] == final_after["total_cost"]
        assert final_before["total_profit"] == final_after["total_profit"]
    finally:
        _cleanup_orphan(db, orphan_resource, orphan_cycle_resource)


def test_orphan_cycle_resource_does_not_change_minimum_demand_behavior(
    db, optimization_cycle, test_products, test_resources,
):
    products_by_name = {p.name: p for p in test_products}
    products_by_name["Test Chair"].minimum_demand = Decimal("2")
    db.commit()

    orphan_resource, orphan_cycle_resource = _add_orphan_cycle_resource(
        db, optimization_cycle,
    )

    try:
        data = _get_test_data(db, optimization_cycle)
        result = solve_optimization(
            optimization_cycle.id,
            data["products"],
            data["cycle_resources"],
            data["requirements"],
        )

        assert result["status"].upper() == "OPTIMAL"

        quantity_by_name = {
            allocation["product_name"]: allocation["quantity"]
            for allocation in result["allocations"]
        }
        assert quantity_by_name["Test Chair"] >= 2
    finally:
        products_by_name["Test Chair"].minimum_demand = Decimal("0")
        db.commit()
        _cleanup_orphan(db, orphan_resource, orphan_cycle_resource)


def test_orphan_cycle_resource_row_itself_is_never_modified(
    db, optimization_cycle, test_products, test_resources,
):
    """
    The fix only changes what calculate_optimized_resource_usage
    RETURNS - it must never write to the database. Confirms the
    orphan CycleResource row (representing an old/inactive/orphaned
    historical resource, exactly the kind of row this task says must
    never be deleted or rewritten) is byte-for-byte unchanged after a
    full optimize cycle.
    """

    orphan_resource, orphan_cycle_resource = _add_orphan_cycle_resource(
        db, optimization_cycle,
    )

    before_available = orphan_cycle_resource.available_quantity
    before_unit_price = orphan_cycle_resource.unit_price
    before_resource_id = orphan_cycle_resource.resource_id

    try:
        data = _get_test_data(db, optimization_cycle)
        result = solve_optimization(
            optimization_cycle.id,
            data["products"],
            data["cycle_resources"],
            data["requirements"],
        )
        build_optimization_result(
            optimization_cycle.id,
            data["products"],
            data["cycle_resources"],
            data["requirements"],
            result["allocations"],
            result["status"],
        )

        db.expire_all()
        refreshed = db.get(CycleResource, orphan_cycle_resource.id)
        assert refreshed is not None  # not deleted
        assert refreshed.available_quantity == before_available
        assert refreshed.unit_price == before_unit_price
        assert refreshed.resource_id == before_resource_id

        refreshed_resource = db.get(Resource, orphan_resource.id)
        assert refreshed_resource is not None  # not deleted
        assert refreshed_resource.is_active is True
    finally:
        db.expire_all()
        orphan_cycle_resource = db.get(CycleResource, orphan_cycle_resource.id)
        orphan_resource = db.get(Resource, orphan_resource.id)
        _cleanup_orphan(db, orphan_resource, orphan_cycle_resource)

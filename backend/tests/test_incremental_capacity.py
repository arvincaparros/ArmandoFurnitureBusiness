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

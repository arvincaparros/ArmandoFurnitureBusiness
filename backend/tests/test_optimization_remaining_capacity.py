from decimal import Decimal

from app.services.optimization import (
    _exhausted_resources,
    _remaining_cycle_capacity,
    calculate_optimized_resource_usage,
    get_optimization_data,
    validate_minimum_demand_capacity,
)


def _cycle_resource(optimization_cycle, resource_name):
    return next(
        cycle_resource
        for cycle_resource in optimization_cycle.cycle_resources
        if cycle_resource.resource.name == resource_name
    )


def _wood_requirement(requirements, product_id):
    return next(
        requirement
        for requirement, resource in requirements
        if requirement.product_id == product_id
        and resource.name == "Test Wood"
    )


# --- _remaining_cycle_capacity ----------------------------------------


def test_remaining_capacity_without_offset_equals_available_quantity(
    optimization_cycle,
):
    """
    None (no earlier applications this cycle, or any caller not yet
    passing the offset) must reproduce the original full-capacity
    behavior exactly - Test Wood's declared 1250.0000.
    """

    wood = _cycle_resource(optimization_cycle, "Test Wood")

    assert _remaining_cycle_capacity(wood, None) == Decimal("1250.0000")


def test_remaining_capacity_deducts_already_consumed(
    optimization_cycle,
):
    wood = _cycle_resource(optimization_cycle, "Test Wood")

    remaining = _remaining_cycle_capacity(
        wood,
        {wood.resource_id: Decimal("450.0000")},
    )

    assert remaining == Decimal("800.0000")


def test_remaining_capacity_is_exactly_zero_when_fully_consumed(
    optimization_cycle,
):
    wood = _cycle_resource(optimization_cycle, "Test Wood")

    remaining = _remaining_cycle_capacity(
        wood,
        {wood.resource_id: Decimal("1250.0000")},
    )

    assert remaining == Decimal("0")


def test_remaining_capacity_floors_at_zero_when_consumed_exceeds_available(
    optimization_cycle,
):
    """
    Over-consumption (e.g. available_quantity reduced below what was
    already applied) must read as fully spent, never a negative
    constraint bound - matches find_resource_capacity_shortages'
    identical convention on the Apply side.
    """

    wood = _cycle_resource(optimization_cycle, "Test Wood")

    remaining = _remaining_cycle_capacity(
        wood,
        {wood.resource_id: Decimal("999999")},
    )

    assert remaining == Decimal("0")


def test_remaining_capacity_treats_inactive_resource_as_zero(
    optimization_cycle,
):
    """
    An inactive resource is zero capacity BEFORE the offset is even
    considered - matches add_resource_constraints' own convention.
    Mutated in memory only; never committed.
    """

    wood = _cycle_resource(optimization_cycle, "Test Wood")
    wood.resource.is_active = False

    try:
        remaining = _remaining_cycle_capacity(
            wood,
            {wood.resource_id: Decimal("1")},
        )

        assert remaining == Decimal("0")

    finally:
        wood.resource.is_active = True


# --- validate_minimum_demand_capacity ----------------------------------


def test_validate_minimum_demand_capacity_uses_remaining_not_full(
    db, optimization_cycle, test_products,
    test_product_resource_requirements,
):
    """
    The core regression: a minimum-demand vector that fits the FULL
    declared cycle capacity must still be refused once enough of that
    capacity has already been consumed by an earlier application this
    cycle - the pre-solve witness check has to see the same remaining
    figure the LP constraint itself now does.
    """

    data = get_optimization_data(db, optimization_cycle.id)

    chair = next(
        product for product in test_products
        if product.name == "Test Chair"
    )

    wood = _cycle_resource(optimization_cycle, "Test Wood")

    original_minimum = chair.minimum_demand

    try:
        # 15 units fits every one of Test Chair's requirements against
        # the FULL cycle capacity (Wood 15*12=180 <= 1250, Epoxy
        # 15*0.5=7.5 <= 8, Nails 15*0.15=2.25 <= 100, Labor 15*8=120 <=
        # 576 - Epoxy is the tightest at a cap of 16, so 15 is the
        # largest round number that still fits all four). Never
        # committed - this test reads the in-memory value only,
        # exactly like validate_minimum_demand_capacity itself does.
        chair.minimum_demand = Decimal("15")

        # Fits the untouched, full capacity.
        validate_minimum_demand_capacity(
            data["products"],
            data["cycle_resources"],
            data["requirements"],
        )

        # No longer fits once enough Wood is already spent that only
        # 170 remains - 15 units need 180, so this is a Wood-specific
        # shortage even though Epoxy/Nails/Labor are untouched.
        try:
            validate_minimum_demand_capacity(
                data["products"],
                data["cycle_resources"],
                data["requirements"],
                {wood.resource_id: Decimal("1080.0000")},
            )
            assert False, "expected a ValueError naming Test Wood"

        except ValueError as error:
            assert "Test Wood" in str(error)

    finally:
        chair.minimum_demand = original_minimum


def test_validate_minimum_demand_capacity_without_offset_unchanged(
    db, optimization_cycle, test_product_resource_requirements,
):
    """
    None reproduces today's behavior exactly: every product's
    minimum_demand is 0 by fixture default, so the all-zero vector
    trivially fits and this never raises.
    """

    data = get_optimization_data(db, optimization_cycle.id)

    validate_minimum_demand_capacity(
        data["products"],
        data["cycle_resources"],
        data["requirements"],
    )

    validate_minimum_demand_capacity(
        data["products"],
        data["cycle_resources"],
        data["requirements"],
        None,
    )


# --- calculate_optimized_resource_usage --------------------------------


def test_resource_usage_reports_cumulative_consumption(
    db, optimization_cycle, test_products,
    test_product_resource_requirements,
):
    """
    The Generate preview must show accurate consumed/remaining/
    utilization: consumed_quantity is what earlier applications this
    cycle already spent, and remaining_quantity is CUMULATIVE
    (available - consumed - this plan's own requirement) - not just
    what this freshly-generated plan alone would use, which is the
    exact "Labor/Table Planer read 100%" misleading-preview bug this
    task fixes.
    """

    data = get_optimization_data(db, optimization_cycle.id)

    chair = next(
        product for product in test_products
        if product.name == "Test Chair"
    )

    wood = _cycle_resource(optimization_cycle, "Test Wood")
    wood_requirement = _wood_requirement(data["requirements"], chair.id)

    allocations = [
        {"product_id": chair.id, "quantity": 2},
    ]

    usage = calculate_optimized_resource_usage(
        allocations,
        data["cycle_resources"],
        data["requirements"],
        {wood.resource_id: Decimal("450.0000")},
    )

    wood_usage = next(
        row for row in usage if row["resource_id"] == wood.resource_id
    )

    required = wood_requirement.quantity_required * Decimal("2")

    assert wood_usage["consumed_quantity"] == Decimal("450.0000")
    assert wood_usage["required_quantity"] == required
    assert wood_usage["available_quantity"] == Decimal("1250.0000")
    assert wood_usage["remaining_quantity"] == (
        Decimal("1250.0000") - Decimal("450.0000") - required
    )


def test_resource_usage_without_offset_unchanged(
    db, optimization_cycle, test_products,
    test_product_resource_requirements,
):
    """
    None reproduces today's behavior exactly: consumed_quantity is 0
    and remaining_quantity is computed from `allocations` alone.
    """

    data = get_optimization_data(db, optimization_cycle.id)

    chair = next(
        product for product in test_products
        if product.name == "Test Chair"
    )

    wood_requirement = _wood_requirement(data["requirements"], chair.id)

    allocations = [
        {"product_id": chair.id, "quantity": 2},
    ]

    usage = calculate_optimized_resource_usage(
        allocations,
        data["cycle_resources"],
        data["requirements"],
    )

    wood_usage = next(
        row for row in usage
        if row["resource_name"] == "Test Wood"
    )

    required = wood_requirement.quantity_required * Decimal("2")

    assert wood_usage["consumed_quantity"] == Decimal("0")
    assert wood_usage["remaining_quantity"] == (
        Decimal("1250.0000") - required
    )


# --- _exhausted_resources ------------------------------------------
#
# Backs apply_optimization's "no applicable product-level results"
# explanation: which resource(s), if any, are provably at zero
# remaining capacity - used to tell the student WHY, not just THAT,
# no further production is possible.


def test_exhausted_resources_identifies_a_fully_consumed_resource(
    optimization_cycle,
):
    wood = _cycle_resource(optimization_cycle, "Test Wood")

    exhausted = _exhausted_resources(
        optimization_cycle.cycle_resources,
        {wood.resource_id: wood.available_quantity},
    )

    assert exhausted == [
        {"resource_name": "Test Wood", "unit": "kg"},
    ]


def test_exhausted_resources_never_names_a_resource_with_capacity_left(
    optimization_cycle,
):
    """
    Avoid misleading shortage messages when some resources still have
    capacity: a resource that is not fully consumed must never appear,
    even alongside one that genuinely is.
    """

    wood = _cycle_resource(optimization_cycle, "Test Wood")
    epoxy = _cycle_resource(optimization_cycle, "Test Epoxy")

    exhausted = _exhausted_resources(
        optimization_cycle.cycle_resources,
        {
            wood.resource_id: wood.available_quantity,
            # Epoxy has plenty left - 1 out of 8.0000 consumed.
            epoxy.resource_id: Decimal("1.0000"),
        },
    )

    assert exhausted == [
        {"resource_name": "Test Wood", "unit": "kg"},
    ]


def test_exhausted_resources_empty_when_nothing_is_fully_consumed(
    optimization_cycle,
):
    """
    No provable zero-capacity resource at all - the caller must fall
    back to the generic message rather than fabricate a specific
    explanation the numbers do not actually support.
    """

    wood = _cycle_resource(optimization_cycle, "Test Wood")

    exhausted = _exhausted_resources(
        optimization_cycle.cycle_resources,
        {wood.resource_id: Decimal("1.0000")},
    )

    assert exhausted == []


def test_exhausted_resources_treats_over_consumption_as_exhausted(
    optimization_cycle,
):
    """
    already_consumed exceeding available_quantity (e.g. capacity was
    reduced below what was already applied) must still be reported as
    exhausted, not skipped - _remaining_cycle_capacity's own floor is
    what makes this work, not a separate check here.
    """

    wood = _cycle_resource(optimization_cycle, "Test Wood")

    exhausted = _exhausted_resources(
        optimization_cycle.cycle_resources,
        {wood.resource_id: Decimal("999999")},
    )

    assert exhausted == [
        {"resource_name": "Test Wood", "unit": "kg"},
    ]

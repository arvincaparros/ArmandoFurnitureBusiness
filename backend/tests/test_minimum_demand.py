from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.database.models import (
    CycleResource,
    OptimizationResult,
    OptimizationRun,
    Product,
    ProductionAllocation,
    ProductionCycle,
    ProductResourceRequirement,
    Resource,
)

from app.services.optimization import (
    create_decision_variables,
    get_optimization_data,
    solve_optimization,
    validate_minimum_demand_resource_availability,
)


FINALIZED_MINIMUM_DEMAND = {
    "Dining Table (4 seater)": Decimal("1"),
    "Dining Table (6 seater)": Decimal("1"),
    "Dining Table (8 seater)": Decimal("0"),
    "Ordinary Table": Decimal("3"),
    "Bed Frame": Decimal("2"),
    "Door (60x210)": Decimal("5"),
    "Door (70x210)": Decimal("5"),
    "Door (80x210)": Decimal("4"),
    "Door (90x210)": Decimal("4"),
    "High Chair": Decimal("2"),
    "Ordinary Chair": Decimal("3"),
}


# --- A. Product/model/migration ---------------------------------------


def test_product_minimum_demand_defaults_to_zero(test_products):
    for product in test_products:
        assert product.minimum_demand == Decimal("0")


def test_finalized_products_have_correct_minimum_demand(db):
    products_by_name = {
        product.name: product
        for product in db.scalars(select(Product)).all()
    }

    for name, expected in FINALIZED_MINIMUM_DEMAND.items():
        assert products_by_name[name].minimum_demand == expected


# --- B. Decision variables are hard-floored at minimum_demand --------------


def test_decision_variable_lowbound_equals_minimum_demand(
    db,
    test_products,
):
    """
    minimum_demand is wired in directly as each variable's lowBound -
    a hard ILP requirement, not a soft target. A product with
    minimum_demand == 0 still gets lowBound == 0 (quantity 0 stays
    legal for it).
    """

    products_by_name = {p.name: p for p in test_products}

    products_by_name["Test Dining Table"].minimum_demand = Decimal("7")
    products_by_name["Test Chair"].minimum_demand = Decimal("0")
    products_by_name["Test Bed Frame"].minimum_demand = Decimal("3")
    db.commit()

    for product in test_products:
        db.refresh(product)

    # Deliberately reversed from DB/insertion order - proves the
    # mapping is keyed by product identity, not list position.
    shuffled = list(reversed(test_products))

    variables = create_decision_variables(shuffled)

    expected_lowbound_by_name = {
        "Test Dining Table": 7,
        "Test Chair": 0,
        "Test Bed Frame": 3,
    }

    for product in test_products:
        variable = variables[product.id]
        assert variable.lowBound == expected_lowbound_by_name[product.name]
        assert variable.cat == "Integer"


# --- C. Successful optimization (all minimums achievable) -----------------


def test_optimization_respects_minimum_demand_while_maximizing_profit(
    db,
    optimization_cycle,
    test_products,
    test_resources,
):
    products_by_name = {p.name: p for p in test_products}

    products_by_name["Test Chair"].minimum_demand = Decimal("2")
    products_by_name["Test Dining Table"].minimum_demand = Decimal("0")
    products_by_name["Test Bed Frame"].minimum_demand = Decimal("0")
    db.commit()

    data = get_optimization_data(db, optimization_cycle.id)

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
    shortfall_by_name = {
        allocation["product_name"]: allocation["shortfall"]
        for allocation in result["allocations"]
    }

    for product in test_products:
        assert quantity_by_name[product.name] >= product.minimum_demand
        assert isinstance(quantity_by_name[product.name], int)
        # A hard-satisfied minimum is always reported with zero shortfall.
        assert shortfall_by_name[product.name] == Decimal("0")

    # Test Dining Table's minimum is 0 - legitimately allowed to stay 0.
    assert quantity_by_name["Test Dining Table"] >= 0

    # The optimizer is free to exceed a minimum when resources/profit
    # allow it - Test Chair's minimum is 2 but nothing caps it there.
    assert quantity_by_name["Test Chair"] >= 2

    # Independently re-verify every resource constraint still holds.
    available_by_name = {
        cr.resource.name: cr.available_quantity
        for cr in data["cycle_resources"]
    }

    consumption_by_resource: dict[str, Decimal] = {}
    for requirement, resource in data["requirements"]:
        qty = Decimal(str(quantity_by_name[
            next(
                p.name for p in test_products if p.id == requirement.product_id
            )
        ]))
        consumption_by_resource[resource.name] = (
            consumption_by_resource.get(resource.name, Decimal("0"))
            + requirement.quantity_required * qty
        )

    for name, consumed in consumption_by_resource.items():
        assert consumed <= available_by_name[name], (
            f"{name}: consumed {consumed} > available "
            f"{available_by_name[name]}"
        )


def test_minimum_demand_zero_allows_zero_quantity(
    db,
    optimization_cycle,
    test_products,
    test_resources,
):
    """
    A product with minimum_demand == 0 may legitimately be produced at
    0 - the restored hard bound must never implicitly require a
    positive quantity for a product with no minimum.
    """

    products_by_name = {p.name: p for p in test_products}
    products_by_name["Test Chair"].minimum_demand = Decimal("0")
    products_by_name["Test Dining Table"].minimum_demand = Decimal("0")
    products_by_name["Test Bed Frame"].minimum_demand = Decimal("0")
    db.commit()

    data = get_optimization_data(db, optimization_cycle.id)

    result = solve_optimization(
        optimization_cycle.id,
        data["products"],
        data["cycle_resources"],
        data["requirements"],
    )

    assert result["status"].upper() == "OPTIMAL"

    for allocation in result["allocations"]:
        assert allocation["quantity"] >= 0
        assert allocation["shortfall"] == Decimal("0")


# --- D. Minimum-capacity shortage: plan rejected, nothing saved -----------


def test_minimum_demand_capacity_shortage_triggers_adaptive_optimization(
    client,
    db,
    optimization_cycle,
    test_products,
):
    """
    Adaptive minimum demand (approved v2 plan): when the exact
    original minimum-demand vector cannot be satisfied simultaneously,
    the optimizer no longer rejects the whole plan - it switches to
    the five-stage adaptive model instead. Both Test Chair and Test
    Dining Table's stated minimums are individually larger than this
    cycle's Epoxy/Wood capacity respectively, so neither can be fully
    met - but full COVERAGE (>=1 unit for every eligible product,
    including zero-minimum Test Bed Frame) is still easily achievable
    given how much capacity remains once minimums are set this high.
    """

    products_by_name = {p.name: p for p in test_products}

    # Test Chair needs 0.5 Epoxy/unit, only 8 Epoxy available -> minimum
    # 20 needs 10 Epoxy, a clean shortage.
    chair = products_by_name["Test Chair"]
    chair.minimum_demand = Decimal("20")

    # Test Dining Table needs 45 Wood/unit, only 1250 Wood available ->
    # minimum 30 needs 1350 Wood, a second, independent shortage.
    dining_table = products_by_name["Test Dining Table"]
    dining_table.minimum_demand = Decimal("30")

    bed_frame = products_by_name["Test Bed Frame"]

    db.commit()

    response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )

    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "OPTIMAL"

    allocations_by_id = {
        allocation["product_id"]: allocation
        for allocation in body["allocations"]
    }

    chair_allocation = allocations_by_id[chair.id]
    dining_table_allocation = allocations_by_id[dining_table.id]
    bed_frame_allocation = allocations_by_id[bed_frame.id]

    # Neither over-stretched minimum can be fully met - both must show
    # a real, positive, unmet-demand shortfall, never silently 0.
    assert chair_allocation["quantity"] < 20
    assert Decimal(str(chair_allocation["shortfall"])) > Decimal("0")
    assert dining_table_allocation["quantity"] < 30
    assert Decimal(str(dining_table_allocation["shortfall"])) > Decimal(
        "0"
    )

    # Full coverage is still achieved for every eligible product,
    # including zero-minimum Test Bed Frame - the headline new
    # behavior this feature exists for.
    assert chair_allocation["quantity"] >= 1
    assert dining_table_allocation["quantity"] >= 1
    assert bed_frame_allocation["quantity"] >= 1

    # Resource capacity must never be exceeded, even under the
    # adaptive model.
    db.refresh(chair)
    db.refresh(dining_table)
    data = get_optimization_data(db, optimization_cycle.id)
    for usage in build_resource_usage_check(
        data["cycle_resources"], data["requirements"], body["allocations"]
    ):
        assert usage["consumed"] <= usage["available"]

    # Original minimum_demand values are never mutated by the solve.
    assert chair.minimum_demand == Decimal("20")
    assert dining_table.minimum_demand == Decimal("30")

    # The run IS persisted now (unlike the old all-or-nothing
    # rejection) - exactly one new OptimizationRun for this cycle.
    runs = db.scalars(
        select(OptimizationRun).where(
            OptimizationRun.production_cycle_id == optimization_cycle.id
        )
    ).all()
    assert len(runs) == 1
    assert runs[0].status == "OPTIMAL"


# --- E. Forecast below minimum: plan rejected ------------------------------


def test_forecast_below_minimum_triggers_adaptive_optimization(
    db,
    optimization_cycle,
    test_products,
    test_resources,
):
    """
    Adaptive minimum demand: a forecast ceiling below the stated
    minimum makes the exact original vector infeasible (the product
    can never legally reach its own minimum, no matter how much
    resource capacity exists) - the optimizer now adapts instead of
    rejecting. Test Chair is the only positive-minimum product here,
    so fairness has nothing to balance against: it should land exactly
    at its forecast ceiling (4), the best it can do, with the
    remaining 1 unit of its minimum (5) reported as unmet demand.
    """

    products_by_name = {p.name: p for p in test_products}
    chair = products_by_name["Test Chair"]
    chair.minimum_demand = Decimal("5")
    db.commit()
    db.refresh(chair)

    data = get_optimization_data(db, optimization_cycle.id)

    result = solve_optimization(
        optimization_cycle.id,
        data["products"],
        data["cycle_resources"],
        data["requirements"],
        forecast={chair.id: Decimal("4")},
    )

    assert result["status"] == "Optimal"

    allocation = next(
        a for a in result["allocations"] if a["product_id"] == chair.id
    )

    assert allocation["quantity"] == 4
    assert allocation["shortfall"] == Decimal("1")

    # Original minimum_demand is untouched.
    db.refresh(chair)
    assert chair.minimum_demand == Decimal("5")

    for usage in build_resource_usage_check(
        data["cycle_resources"], data["requirements"], result["allocations"]
    ):
        assert usage["consumed"] <= usage["available"]


def test_forecast_equal_to_minimum_is_feasible(
    db,
    optimization_cycle,
    test_products,
    test_resources,
):
    products_by_name = {p.name: p for p in test_products}
    chair = products_by_name["Test Chair"]
    chair.minimum_demand = Decimal("5")
    db.commit()
    db.refresh(chair)

    data = get_optimization_data(db, optimization_cycle.id)

    result = solve_optimization(
        optimization_cycle.id,
        data["products"],
        data["cycle_resources"],
        data["requirements"],
        forecast={chair.id: Decimal("5")},
    )

    allocation = next(
        a for a in result["allocations"] if a["product_id"] == chair.id
    )

    assert allocation["quantity"] == 5
    assert allocation["shortfall"] == Decimal("0")


def test_forecast_absent_entry_has_no_ceiling(
    db,
    optimization_cycle,
    test_products,
    test_resources,
):
    """
    Matches the router's existing behavior of excluding forecast_quantity
    == 0 entries entirely (production.py::optimize_production) - a
    product with no key in the forecast dict has no ceiling at all
    today, so it's free to clear its own minimum with resources alone.
    """

    products_by_name = {p.name: p for p in test_products}
    chair = products_by_name["Test Chair"]
    chair.minimum_demand = Decimal("5")
    db.commit()
    db.refresh(chair)

    data = get_optimization_data(db, optimization_cycle.id)

    result = solve_optimization(
        optimization_cycle.id,
        data["products"],
        data["cycle_resources"],
        data["requirements"],
        forecast={},
    )

    allocation = next(
        a for a in result["allocations"] if a["product_id"] == chair.id
    )

    assert allocation["quantity"] >= 5
    assert allocation["shortfall"] == Decimal("0")


# --- F. Resource lifecycle ---------------------------------------------


def test_minimum_demand_inactive_required_resource_triggers_adaptive_optimization(
    client,
    db,
    optimization_cycle,
    test_products,
    test_resources,
):
    """
    An inactive resource is modeled as zero available capacity
    (add_resource_constraints) - a product whose minimum demand needs
    a positive amount of it can never reach that minimum. Under the
    adaptive model this is no longer a whole-cycle rejection: Test
    Nails is required by all three test_products, so deactivating it
    forces every one of them to a production quantity of 0 (nothing
    can be produced without it) - Test Chair's stated minimum of 1
    shows up as a real, reported shortfall instead of a 400.
    """

    products_by_name = {p.name: p for p in test_products}
    resources_by_name = {r.name: r for r in test_resources}

    chair = products_by_name["Test Chair"]
    chair.minimum_demand = Decimal("1")
    resources_by_name["Test Nails"].is_active = False
    db.commit()

    try:
        response = client.post(
            f"/api/production-cycles/{optimization_cycle.id}/optimize",
            json={"objective": "MAX_PROFIT"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "OPTIMAL"

        chair_allocation = next(
            a for a in body["allocations"] if a["product_id"] == chair.id
        )
        assert chair_allocation["quantity"] == 0
        assert Decimal(str(chair_allocation["shortfall"])) == Decimal("1")

        # Every product needs Nails - all are capped at 0, never a
        # fabricated nonzero quantity against zero real capacity.
        for allocation in body["allocations"]:
            assert allocation["quantity"] == 0

        db.refresh(chair)
        assert chair.minimum_demand == Decimal("1")
    finally:
        resources_by_name["Test Nails"].is_active = True
        db.commit()


def test_minimum_demand_blocked_by_unpriced_resource_this_cycle(
    client,
    db,
    optimization_cycle,
    test_products,
    test_resources,
):
    """
    Distinct from the inactive case above: a resource with NO
    CycleResource row at all this cycle has no known capacity to model
    as zero (not even a real zero) and no known cost - there's nothing
    safe to fall back to, so this remains a hard validation error.
    """

    products_by_name = {p.name: p for p in test_products}
    resources_by_name = {r.name: r for r in test_resources}

    products_by_name["Test Chair"].minimum_demand = Decimal("1")
    db.commit()

    nails_cycle_resource = db.scalar(
        select(CycleResource).where(
            CycleResource.production_cycle_id == optimization_cycle.id,
            CycleResource.resource_id == resources_by_name["Test Nails"].id,
        )
    )
    removed_available = nails_cycle_resource.available_quantity
    removed_price = nails_cycle_resource.unit_price
    db.delete(nails_cycle_resource)
    db.commit()

    try:
        response = client.post(
            f"/api/production-cycles/{optimization_cycle.id}/optimize",
            json={"objective": "MAX_PROFIT"},
        )

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "Test Chair" in detail
        assert "Test Nails" in detail
        assert "unpriced" in detail
    finally:
        db.add(
            CycleResource(
                production_cycle_id=optimization_cycle.id,
                resource_id=resources_by_name["Test Nails"].id,
                available_quantity=removed_available,
                unit_price=removed_price,
            )
        )
        db.commit()


def test_minimum_demand_optimization_recovers_after_resource_reactivated(
    client,
    db,
    optimization_cycle,
    test_products,
    test_resources,
):
    """
    Shortfall from an adaptive run (Test Nails deactivated, Test
    Chair's minimum unreachable) must clear back to 0 once the
    resource is reactivated - the second call lands back on the
    Phase 1 (hard-minimum) fast path, since the vector is simultaneously
    feasible again.
    """

    products_by_name = {p.name: p for p in test_products}
    resources_by_name = {r.name: r for r in test_resources}

    products_by_name["Test Chair"].minimum_demand = Decimal("1")
    resources_by_name["Test Nails"].is_active = False
    db.commit()

    adaptive_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )
    assert adaptive_response.status_code == 200
    adaptive_data = adaptive_response.json()
    assert adaptive_data["status"] == "OPTIMAL"

    chair_before = next(
        a
        for a in adaptive_data["allocations"]
        if a["product_name"] == "Test Chair"
    )
    assert chair_before["quantity"] == 0
    assert Decimal(str(chair_before["shortfall"])) == Decimal("1")

    resources_by_name["Test Nails"].is_active = True
    db.commit()

    recovered = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )

    assert recovered.status_code == 200
    recovered_data = recovered.json()
    assert recovered_data["status"] == "OPTIMAL"

    chair_after = next(
        a
        for a in recovered_data["allocations"]
        if a["product_name"] == "Test Chair"
    )
    assert chair_after["quantity"] >= 1
    assert Decimal(str(chair_after["shortfall"])) == Decimal("0")


def test_inactive_resource_for_one_product_blocks_only_that_products_coverage(
    db,
    optimization_cycle,
    test_products,
    test_resources,
):
    """
    Distinguishes an inactive resource shared by every product from
    one that only a single product depends on. Under the adaptive
    model this is no longer an error-message distinction - it's now
    literally true at the allocation level: Test Chair-Only Resource
    is needed by nothing except Test Chair, so only Test Chair is
    forced to 0 (and reports its full minimum as shortfall); Test
    Dining Table and Test Bed Frame don't touch this resource at all
    and must still reach full coverage normally.
    """

    products_by_name = {p.name: p for p in test_products}
    chair = products_by_name["Test Chair"]
    dining_table = products_by_name["Test Dining Table"]
    bed_frame = products_by_name["Test Bed Frame"]

    chair.minimum_demand = Decimal("2")
    db.commit()

    chair_only_resource = Resource(
        name="Test Chair-Only Resource",
        resource_type="material",
        unit="pcs",
        is_active=False,
    )
    db.add(chair_only_resource)
    db.commit()
    db.refresh(chair_only_resource)

    chair_only_cycle_resource = CycleResource(
        production_cycle_id=optimization_cycle.id,
        resource_id=chair_only_resource.id,
        available_quantity=Decimal("50.0000"),
        unit_price=Decimal("5.00"),
    )
    db.add(chair_only_cycle_resource)

    chair_only_requirement = ProductResourceRequirement(
        product_id=chair.id,
        resource_id=chair_only_resource.id,
        quantity_required=Decimal("1.0000"),
    )
    db.add(chair_only_requirement)
    db.commit()

    try:
        data = get_optimization_data(db, optimization_cycle.id)

        result = solve_optimization(
            optimization_cycle.id,
            data["products"],
            data["cycle_resources"],
            data["requirements"],
        )

        assert result["status"] == "Optimal"

        allocations_by_id = {
            a["product_id"]: a for a in result["allocations"]
        }

        chair_allocation = allocations_by_id[chair.id]
        assert chair_allocation["quantity"] == 0
        assert Decimal(str(chair_allocation["shortfall"])) == Decimal("2")

        # Unaffected products still reach full coverage - the inactive,
        # chair-only resource never blocks them.
        assert allocations_by_id[dining_table.id]["quantity"] >= 1
        assert allocations_by_id[bed_frame.id]["quantity"] >= 1

        for usage in build_resource_usage_check(
            data["cycle_resources"],
            data["requirements"],
            result["allocations"],
        ):
            assert usage["consumed"] <= usage["available"]
    finally:
        db.delete(chair_only_requirement)
        db.delete(chair_only_cycle_resource)
        db.delete(chair_only_resource)
        db.commit()


# --- G. Apply / history ------------------------------------------------------


def test_minimum_driven_plan_applies_and_persists_quantities(
    client,
    db,
    optimization_cycle,
    test_products,
):
    products_by_name = {p.name: p for p in test_products}
    products_by_name["Test Chair"].minimum_demand = Decimal("2")
    db.commit()

    optimize_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )
    assert optimize_response.status_code == 200
    assert optimize_response.json()["status"] == "OPTIMAL"

    quantity_by_product_id = {
        allocation["product_id"]: allocation["quantity"]
        for allocation in optimize_response.json()["allocations"]
    }

    apply_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply"
    )
    assert apply_response.status_code == 200

    apply_data = apply_response.json()
    chair = products_by_name["Test Chair"]
    chair_applied = next(
        a for a in apply_data["allocations"] if a["product_id"] == chair.id
    )
    assert Decimal(str(chair_applied["minimum_demand"])) == Decimal("2")
    assert Decimal(str(chair_applied["shortfall"])) == Decimal("0")

    allocations = db.scalars(
        select(ProductionAllocation).where(
            ProductionAllocation.production_cycle_id == optimization_cycle.id
        )
    ).all()

    persisted_by_product_id = {
        allocation.product_id: allocation.quantity
        for allocation in allocations
    }

    assert persisted_by_product_id[chair.id] == Decimal(
        str(quantity_by_product_id[chair.id])
    )
    assert persisted_by_product_id[chair.id] >= chair.minimum_demand

    latest_run = db.scalar(
        select(OptimizationRun)
        .where(OptimizationRun.production_cycle_id == optimization_cycle.id)
        .order_by(OptimizationRun.id.desc())
    )
    results = db.scalars(
        select(OptimizationResult).where(
            OptimizationResult.optimization_run_id == latest_run.id
        )
    ).all()
    result_by_product_id = {
        result.product_id: result.recommended_quantity
        for result in results
    }

    assert result_by_product_id[chair.id] == Decimal(
        str(quantity_by_product_id[chair.id])
    )

    # OptimizationResult's minimum_demand/shortfall properties (not
    # persisted columns - see app/database/models.py) must agree with
    # the just-applied response above.
    chair_result = next(r for r in results if r.product_id == chair.id)
    assert chair_result.minimum_demand == Decimal("2")
    assert chair_result.shortfall == Decimal("0")


def test_rejected_optimization_leaves_existing_allocations_untouched(
    client,
    db,
    optimization_cycle,
    test_products,
    test_resources,
):
    """
    Generate and apply a feasible plan first, then attempt a second
    /optimize call that's still genuinely rejected even under the
    adaptive model - a resource with no CycleResource row at all this
    cycle is a data-completeness problem, not a capacity shortfall the
    adaptive optimizer can gracefully absorb (see
    validate_minimum_demand_resource_availability). The rejected
    second call must leave the previously applied ProductionAllocation
    rows completely untouched.
    """

    products_by_name = {p.name: p for p in test_products}
    resources_by_name = {r.name: r for r in test_resources}
    products_by_name["Test Chair"].minimum_demand = Decimal("2")
    db.commit()

    optimize_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )
    assert optimize_response.status_code == 200

    apply_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply"
    )
    assert apply_response.status_code == 200

    allocations_before = {
        allocation.product_id: allocation.quantity
        for allocation in db.scalars(
            select(ProductionAllocation).where(
                ProductionAllocation.production_cycle_id
                == optimization_cycle.id
            )
        ).all()
    }
    assert allocations_before

    # Remove Test Nails' CycleResource row entirely - a data-
    # completeness problem that remains a hard rejection regardless of
    # Phase 1/2.
    nails_cycle_resource = db.scalar(
        select(CycleResource).where(
            CycleResource.production_cycle_id == optimization_cycle.id,
            CycleResource.resource_id == resources_by_name["Test Nails"].id,
        )
    )
    removed_available = nails_cycle_resource.available_quantity
    removed_price = nails_cycle_resource.unit_price
    db.delete(nails_cycle_resource)
    db.commit()

    try:
        rejected_response = client.post(
            f"/api/production-cycles/{optimization_cycle.id}/optimize",
            json={"objective": "MAX_PROFIT"},
        )
        assert rejected_response.status_code == 400

        allocations_after = {
            allocation.product_id: allocation.quantity
            for allocation in db.scalars(
                select(ProductionAllocation).where(
                    ProductionAllocation.production_cycle_id
                    == optimization_cycle.id
                )
            ).all()
        }

        assert allocations_after == allocations_before
    finally:
        db.add(
            CycleResource(
                production_cycle_id=optimization_cycle.id,
                resource_id=resources_by_name["Test Nails"].id,
                available_quantity=removed_available,
                unit_price=removed_price,
            )
        )
        db.commit()


# --- H. Financial reconciliation --------------------------------


def test_minimum_driven_plan_financials_reconcile(
    client,
    db,
    optimization_cycle,
    test_products,
):
    products_by_name = {p.name: p for p in test_products}
    products_by_name["Test Chair"].minimum_demand = Decimal("2")
    products_by_name["Test Bed Frame"].minimum_demand = Decimal("1")
    db.commit()

    response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )
    assert response.status_code == 200
    data = response.json()

    total_revenue = Decimal(data["total_revenue"])
    total_cost = Decimal(data["total_cost"])
    total_profit = Decimal(data["total_profit"])

    assert total_profit == total_revenue - total_cost

    products_by_id = {p.id: p for p in test_products}
    row_revenue_sum = Decimal("0")
    row_profit_sum = Decimal("0")

    for allocation in data["allocations"]:
        product = products_by_id[allocation["product_id"]]
        quantity = Decimal(str(allocation["quantity"]))
        row_revenue = product.selling_price * quantity
        row_profit = Decimal(allocation["total_profit"])

        assert row_profit == Decimal(allocation["unit_profit"]) * quantity

        row_revenue_sum += row_revenue
        row_profit_sum += row_profit

    assert row_revenue_sum == total_revenue
    assert row_profit_sum == total_profit


# --- I. Profit maximization among feasible minimum-satisfying plans -------


def test_profit_maximized_among_minimum_satisfying_plans(
    db,
    optimization_cycle,
    test_products,
):
    """
    Hand-verified scenario, adapted from the resource-contention case
    that used to prove Stage 2's tie-break under the soft-shortfall
    model. Under the restored hard bound, both minimums are easily
    within the 10-unit Scarce budget (6 + 2 = 8 <= 10), so there is no
    forced shortfall at all - the optimizer must give every product
    AT LEAST its minimum and then spend any remaining Scarce capacity
    on whichever product is most profitable (Test Bed Frame, far
    higher unit_profit than Test Chair).
    """

    products_by_name = {p.name: p for p in test_products}
    chair = products_by_name["Test Chair"]
    bed_frame = products_by_name["Test Bed Frame"]
    dining_table = products_by_name["Test Dining Table"]

    chair.minimum_demand = Decimal("2")
    bed_frame.minimum_demand = Decimal("2")
    db.commit()

    scarce_resource = Resource(
        name="Test Scarce Resource",
        resource_type="material",
        unit="pcs",
        is_active=True,
    )
    db.add(scarce_resource)
    db.commit()
    db.refresh(scarce_resource)

    scarce_cycle_resource = CycleResource(
        production_cycle_id=optimization_cycle.id,
        resource_id=scarce_resource.id,
        available_quantity=Decimal("10.0000"),
        unit_price=Decimal("0.00"),
    )
    db.add(scarce_cycle_resource)

    chair_requirement = ProductResourceRequirement(
        product_id=chair.id,
        resource_id=scarce_resource.id,
        quantity_required=Decimal("1.0000"),
    )
    bed_frame_requirement = ProductResourceRequirement(
        product_id=bed_frame.id,
        resource_id=scarce_resource.id,
        quantity_required=Decimal("1.0000"),
    )
    db.add(chair_requirement)
    db.add(bed_frame_requirement)
    db.commit()

    try:
        data = get_optimization_data(db, optimization_cycle.id)

        result = solve_optimization(
            optimization_cycle.id,
            data["products"],
            data["cycle_resources"],
            data["requirements"],
            forecast={dining_table.id: Decimal("0")},
        )

        assert result["status"] == "Optimal"

        allocations_by_id = {
            a["product_id"]: a for a in result["allocations"]
        }
        chair_allocation = allocations_by_id[chair.id]
        bed_frame_allocation = allocations_by_id[bed_frame.id]

        assert chair_allocation["quantity"] >= 2
        assert bed_frame_allocation["quantity"] >= 2
        assert chair_allocation["shortfall"] == Decimal("0")
        assert bed_frame_allocation["shortfall"] == Decimal("0")

        # All remaining Scarce capacity (10 - 2 - 2 = 6 units) must go
        # to the more profitable product, Bed Frame, not Chair.
        assert bed_frame_allocation["quantity"] == 8
        assert chair_allocation["quantity"] == 2

        # Resource usage must never exceed availability.
        for usage in build_resource_usage_check(
            data["cycle_resources"], data["requirements"], result["allocations"]
        ):
            assert usage["consumed"] <= usage["available"]
    finally:
        db.delete(chair_requirement)
        db.delete(bed_frame_requirement)
        db.delete(scarce_cycle_resource)
        db.delete(scarce_resource)
        db.commit()


def build_resource_usage_check(cycle_resources, requirements, allocations):
    quantity_by_product_id = {
        allocation["product_id"]: allocation["quantity"]
        for allocation in allocations
    }

    consumed_by_resource_id: dict[int, Decimal] = {}
    for requirement, _resource in requirements:
        quantity = quantity_by_product_id.get(requirement.product_id, 0)
        consumed_by_resource_id[requirement.resource_id] = (
            consumed_by_resource_id.get(requirement.resource_id, Decimal("0"))
            + requirement.quantity_required * Decimal(str(quantity))
        )

    checks = []
    for cycle_resource in cycle_resources:
        checks.append(
            {
                "consumed": consumed_by_resource_id.get(
                    cycle_resource.resource_id, Decimal("0")
                ),
                "available": (
                    cycle_resource.available_quantity
                    if cycle_resource.resource.is_active
                    else Decimal("0")
                ),
            }
        )

    return checks


# --- J. Adaptive minimum demand (v2 plan) -----------------------------------


def _build_single_resource_scenario(
    db,
    resource_unit,
    available_quantity,
    unit_price,
    product_specs,
):
    """
    A fully self-contained cycle/resource/product fixture, isolated
    from test_products/test_resources' own Wood/Epoxy/Nails/Labor
    graph - used for the adaptive-model tests below that need
    hand-verifiable exact numbers. product_specs: list of dicts with
    keys name, minimum_demand, requirement_qty, selling_price.
    labor_cost is always 0 and the resource's unit_price is caller-
    controlled, so unit_profit == selling_price whenever unit_price is
    passed as 0 - keeps profit assertions exact.
    """

    resource = Resource(
        name=f"Test Adaptive Resource {id(product_specs)}",
        resource_type="material",
        unit=resource_unit,
        is_active=True,
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)

    cycle = ProductionCycle(
        cycle_date=datetime(2026, 8, 9),
        start_date=datetime(2026, 8, 9),
        end_date=datetime(2026, 8, 9),
        status="PLANNED",
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    cycle_resource = CycleResource(
        production_cycle_id=cycle.id,
        resource_id=resource.id,
        available_quantity=Decimal(str(available_quantity)),
        unit_price=Decimal(str(unit_price)),
    )
    db.add(cycle_resource)
    db.commit()

    products = []
    requirements = []

    for spec in product_specs:
        product = Product(
            name=spec["name"],
            selling_price=Decimal(str(spec["selling_price"])),
            labor_cost=Decimal("0"),
            minimum_demand=Decimal(str(spec["minimum_demand"])),
            is_active=True,
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        products.append(product)

        requirement = ProductResourceRequirement(
            product_id=product.id,
            resource_id=resource.id,
            quantity_required=Decimal(str(spec["requirement_qty"])),
        )
        db.add(requirement)
        requirements.append(requirement)

    db.commit()

    return resource, cycle, cycle_resource, products, requirements


def _cleanup_single_resource_scenario(
    db,
    resource,
    cycle,
    cycle_resource,
    products,
    requirements,
):
    for requirement in requirements:
        db.delete(requirement)

    for product in products:
        db.delete(product)

    db.delete(cycle_resource)
    db.delete(cycle)
    db.delete(resource)
    db.commit()


def test_adaptive_worked_example_matches_hand_verified_plan(db):
    """
    Exact reproduction of the approved v2 plan's worked example
    (docs/investigations/2026-10-12-adaptive-minimum-demand-
    implementation-plan.md, section 9): A (min=5, 4 units/unit,
    $50/unit), B (min=3, 3 units/unit, $30/unit), C (min=0, 2
    units/unit, $10/unit), 25 units of the one shared resource
    available. The full minimum vector needs 29 (infeasible); full
    coverage needs only 9. The plan's exhaustive 15-combination
    enumeration proves A=4, B=2, C=1 (profit $270, 24/25 used) is the
    unique Stage 4 optimum - this test asserts the implementation
    actually reproduces it exactly, not just "some" plausible plan.
    """

    resource, cycle, cycle_resource, products, requirements = (
        _build_single_resource_scenario(
            db,
            resource_unit="units",
            available_quantity=25,
            unit_price=0,
            product_specs=[
                {
                    "name": "Test Adaptive A",
                    "minimum_demand": 5,
                    "requirement_qty": 4,
                    "selling_price": 50,
                },
                {
                    "name": "Test Adaptive B",
                    "minimum_demand": 3,
                    "requirement_qty": 3,
                    "selling_price": 30,
                },
                {
                    "name": "Test Adaptive C",
                    "minimum_demand": 0,
                    "requirement_qty": 2,
                    "selling_price": 10,
                },
            ],
        )
    )

    try:
        data = get_optimization_data(db, cycle.id)

        result = solve_optimization(
            cycle.id,
            data["products"],
            data["cycle_resources"],
            data["requirements"],
        )

        assert result["status"] == "Optimal"

        quantity_by_name = {
            a["product_name"]: a["quantity"] for a in result["allocations"]
        }
        shortfall_by_name = {
            a["product_name"]: a["shortfall"] for a in result["allocations"]
        }

        assert quantity_by_name["Test Adaptive A"] == 4
        assert quantity_by_name["Test Adaptive B"] == 2
        assert quantity_by_name["Test Adaptive C"] == 1
        assert shortfall_by_name["Test Adaptive A"] == Decimal("1")
        assert shortfall_by_name["Test Adaptive B"] == Decimal("1")
        assert shortfall_by_name["Test Adaptive C"] == Decimal("0")

        total_profit = sum(
            Decimal(str(a["total_profit"])) for a in result["allocations"]
        )
        assert total_profit == Decimal("270.0000")

        resource_used = (
            Decimal("4") * quantity_by_name["Test Adaptive A"]
            + Decimal("3") * quantity_by_name["Test Adaptive B"]
            + Decimal("2") * quantity_by_name["Test Adaptive C"]
        )
        assert resource_used == Decimal("24")
        assert resource_used <= Decimal("25")

        # Original minimum_demand values are never mutated.
        for product in products:
            db.refresh(product)
        minimum_by_name = {p.name: p.minimum_demand for p in products}
        assert minimum_by_name["Test Adaptive A"] == Decimal("5")
        assert minimum_by_name["Test Adaptive B"] == Decimal("3")
        assert minimum_by_name["Test Adaptive C"] == Decimal("0")
    finally:
        _cleanup_single_resource_scenario(
            db, resource, cycle, cycle_resource, products, requirements
        )


def test_adaptive_stage3_resolves_coverage_tie_by_profitability(db):
    """
    Minimal illustration of Stage 3 (profitability coverage
    tie-break), matching the v2 plan's supplementary example: X
    ($20/unit) and Y ($15/unit) each individually require all 6 units
    of a shared resource (Resource_XY) - covering both needs 12
    (infeasible), covering either alone needs exactly 6 (feasible).
    Both achieve the same total-coverage count: Stage 3 must pick the
    more profitable one, X.

    X and Y are both zero-minimum, so on their own they would never
    make the overall minimum vector infeasible - the vector-feasibility
    witness only looks at positive-minimum products, so a tie-break
    test built from zero-minimum products alone silently falls through
    to the unmodified Phase 1 fast path and never exercises Stage 3 at
    all. A third product, P, is added on its OWN separate resource
    (Resource_P, 2 units available) with minimum_demand=5 requiring 1
    unit/unit - P's own full minimum (5) exceeds its own resource's
    capacity (2), which by itself makes the whole vector infeasible
    and forces genuine Phase 2 routing, while P's single unit of
    coverage (1 <= 2) is independent of X/Y's shared resource and does
    not disturb their tie-break.
    """

    resource_xy = Resource(
        name="Test Adaptive Resource XY",
        resource_type="material",
        unit="units",
        is_active=True,
    )
    resource_p = Resource(
        name="Test Adaptive Resource P",
        resource_type="material",
        unit="units",
        is_active=True,
    )
    db.add_all([resource_xy, resource_p])
    db.commit()
    db.refresh(resource_xy)
    db.refresh(resource_p)

    cycle = ProductionCycle(
        cycle_date=datetime(2026, 8, 9),
        start_date=datetime(2026, 8, 9),
        end_date=datetime(2026, 8, 9),
        status="PLANNED",
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    cycle_resource_xy = CycleResource(
        production_cycle_id=cycle.id,
        resource_id=resource_xy.id,
        available_quantity=Decimal("6"),
        unit_price=Decimal("0"),
    )
    cycle_resource_p = CycleResource(
        production_cycle_id=cycle.id,
        resource_id=resource_p.id,
        available_quantity=Decimal("2"),
        unit_price=Decimal("0"),
    )
    db.add_all([cycle_resource_xy, cycle_resource_p])
    db.commit()

    product_x = Product(
        name="Test Adaptive X",
        selling_price=Decimal("20"),
        labor_cost=Decimal("0"),
        minimum_demand=Decimal("0"),
        is_active=True,
    )
    product_y = Product(
        name="Test Adaptive Y",
        selling_price=Decimal("15"),
        labor_cost=Decimal("0"),
        minimum_demand=Decimal("0"),
        is_active=True,
    )
    product_p = Product(
        name="Test Adaptive P",
        selling_price=Decimal("10"),
        labor_cost=Decimal("0"),
        minimum_demand=Decimal("5"),
        is_active=True,
    )
    db.add_all([product_x, product_y, product_p])
    db.commit()
    db.refresh(product_x)
    db.refresh(product_y)
    db.refresh(product_p)

    requirement_x = ProductResourceRequirement(
        product_id=product_x.id,
        resource_id=resource_xy.id,
        quantity_required=Decimal("6"),
    )
    requirement_y = ProductResourceRequirement(
        product_id=product_y.id,
        resource_id=resource_xy.id,
        quantity_required=Decimal("6"),
    )
    requirement_p = ProductResourceRequirement(
        product_id=product_p.id,
        resource_id=resource_p.id,
        quantity_required=Decimal("1"),
    )
    db.add_all([requirement_x, requirement_y, requirement_p])
    db.commit()

    products = [product_x, product_y, product_p]
    requirements = [requirement_x, requirement_y, requirement_p]

    try:
        data = get_optimization_data(db, cycle.id)

        result = solve_optimization(
            cycle.id,
            data["products"],
            data["cycle_resources"],
            data["requirements"],
        )

        assert result["status"] == "Optimal"

        quantity_by_name = {
            a["product_name"]: a["quantity"] for a in result["allocations"]
        }

        # P's own-resource infeasibility (5 > 2) is what forces this
        # scenario through the adaptive path at all - Stage 5's profit
        # objective then lets P use its full 2-unit resource capacity
        # (still short of its minimum_demand=5), since nothing else
        # competes for Resource_P.
        assert quantity_by_name["Test Adaptive P"] == 2

        assert quantity_by_name["Test Adaptive X"] >= 1
        assert quantity_by_name["Test Adaptive Y"] == 0
    finally:
        for requirement in requirements:
            db.delete(requirement)
        for product in products:
            db.delete(product)
        db.delete(cycle_resource_xy)
        db.delete(cycle_resource_p)
        db.delete(cycle)
        db.delete(resource_xy)
        db.delete(resource_p)
        db.commit()


def test_adaptive_strict_priority_never_sacrifices_positive_minimum_coverage(
    db,
):
    """
    Rule C/D: strict priority, not a weighted sum. P (positive-minimum
    of 2, needs all 5 units of the resource for even 1 unit, so its
    full minimum of 2 - needing 10 - is itself infeasible and genuinely
    routes this through Phase 2, not Phase 1) competes against three
    zero-minimum products (Z1/Z2/Z3, 2 units/unit each - covering any
    two of them fits in 5, covering P does not leave room for any). A
    weighted-sum model (e.g. weight 2 vs 1) could prefer covering 2-3
    zero-minimum products over the single positive-minimum one; this
    model must never make that trade - P's coverage is decided in
    Stage 1, total isolation, before any zero-minimum product is even
    considered.
    """

    resource, cycle, cycle_resource, products, requirements = (
        _build_single_resource_scenario(
            db,
            resource_unit="units",
            available_quantity=5,
            unit_price=0,
            product_specs=[
                {
                    "name": "Test Adaptive P",
                    "minimum_demand": 2,
                    "requirement_qty": 5,
                    "selling_price": 10,
                },
                {
                    "name": "Test Adaptive Z1",
                    "minimum_demand": 0,
                    "requirement_qty": 2,
                    "selling_price": 10,
                },
                {
                    "name": "Test Adaptive Z2",
                    "minimum_demand": 0,
                    "requirement_qty": 2,
                    "selling_price": 10,
                },
                {
                    "name": "Test Adaptive Z3",
                    "minimum_demand": 0,
                    "requirement_qty": 2,
                    "selling_price": 10,
                },
            ],
        )
    )

    try:
        data = get_optimization_data(db, cycle.id)

        result = solve_optimization(
            cycle.id,
            data["products"],
            data["cycle_resources"],
            data["requirements"],
        )

        assert result["status"] == "Optimal"

        quantity_by_name = {
            a["product_name"]: a["quantity"] for a in result["allocations"]
        }

        # P must be covered - strict priority, never traded away for a
        # higher zero-minimum coverage count.
        assert quantity_by_name["Test Adaptive P"] >= 1

        # Resource is fully consumed by P's own requirement (5 of 5),
        # so none of the zero-minimum products can fit at all - this
        # confirms the resource math, not just the priority rule.
        total_used = Decimal("5") * quantity_by_name["Test Adaptive P"]
        for name in (
            "Test Adaptive Z1",
            "Test Adaptive Z2",
            "Test Adaptive Z3",
        ):
            total_used += Decimal("2") * quantity_by_name[name]
        assert total_used <= Decimal("5")
    finally:
        _cleanup_single_resource_scenario(
            db, resource, cycle, cycle_resource, products, requirements
        )


def test_adaptive_zero_minimum_product_covered_when_full_coverage_feasible(
    db,
):
    """
    Rule C: a zero-minimum product must still reach >=1 unit whenever
    there is leftover resource capacity for it, once the positive-
    minimum product's own (reduced, Stage-1-covered) share is set
    aside - not left at a default 0 just because it has no stated
    minimum. available_quantity=5 (not 20) is deliberate: at 20 the
    positive-minimum product's full minimum of 2*3=6 is itself
    feasible, so the whole vector is trivially feasible and this
    scenario would silently route through the unmodified Phase 1 fast
    path instead of exercising the adaptive pipeline at all. At 5,
    6 > 5 makes the full vector genuinely infeasible (forcing Phase 2),
    while Stage 1 can still cover the positive-minimum product at 1
    unit (3 <= 5), leaving exactly 2 units of capacity - enough for
    the zero-minimum product to also be covered.
    """

    resource, cycle, cycle_resource, products, requirements = (
        _build_single_resource_scenario(
            db,
            resource_unit="units",
            available_quantity=5,
            unit_price=0,
            product_specs=[
                {
                    "name": "Test Adaptive Minimum Product",
                    "minimum_demand": 2,
                    "requirement_qty": 3,
                    "selling_price": 10,
                },
                {
                    "name": "Test Adaptive Zero Product",
                    "minimum_demand": 0,
                    "requirement_qty": 1,
                    "selling_price": 1,
                },
            ],
        )
    )

    try:
        data = get_optimization_data(db, cycle.id)

        result = solve_optimization(
            cycle.id,
            data["products"],
            data["cycle_resources"],
            data["requirements"],
        )

        assert result["status"] == "Optimal"

        quantity_by_name = {
            a["product_name"]: a["quantity"] for a in result["allocations"]
        }

        assert quantity_by_name["Test Adaptive Zero Product"] >= 1
        assert quantity_by_name["Test Adaptive Minimum Product"] >= 1
    finally:
        _cleanup_single_resource_scenario(
            db, resource, cycle, cycle_resource, products, requirements
        )


def test_adaptive_resource_capacity_never_exceeded_under_stress(db):
    """
    A deliberately over-subscribed scenario (six positive-minimum
    products whose combined minimums vastly exceed the one shared
    resource) - every one of Stages 1-5 must return Optimal (never
    Infeasible, per the plan's formal proof that each stage's own
    optimum is always a feasible witness for the next), and the final
    plan's total resource consumption must never exceed what's
    available.
    """

    specs = [
        {
            "name": f"Test Adaptive Stress {i}",
            "minimum_demand": 10,
            "requirement_qty": 7,
            "selling_price": 5 + i,
        }
        for i in range(6)
    ]

    resource, cycle, cycle_resource, products, requirements = (
        _build_single_resource_scenario(
            db,
            resource_unit="units",
            available_quantity=15,
            unit_price=0,
            product_specs=specs,
        )
    )

    try:
        data = get_optimization_data(db, cycle.id)

        result = solve_optimization(
            cycle.id,
            data["products"],
            data["cycle_resources"],
            data["requirements"],
        )

        assert result["status"] == "Optimal"

        total_used = sum(
            Decimal("7") * Decimal(str(a["quantity"]))
            for a in result["allocations"]
        )
        assert total_used <= Decimal("15")

        assert any(a["quantity"] >= 1 for a in result["allocations"])
    finally:
        _cleanup_single_resource_scenario(
            db, resource, cycle, cycle_resource, products, requirements
        )


def test_adaptive_optimization_is_deterministic(db):
    """
    Rule/plan requirement: the same inputs must always produce the
    same (coverage, fairness, final quantities) result - calling
    solve_optimization twice in a row on an unchanged, infeasible-
    minimum scenario must return byte-identical allocations.
    """

    resource, cycle, cycle_resource, products, requirements = (
        _build_single_resource_scenario(
            db,
            resource_unit="units",
            available_quantity=25,
            unit_price=0,
            product_specs=[
                {
                    "name": "Test Adaptive A",
                    "minimum_demand": 5,
                    "requirement_qty": 4,
                    "selling_price": 50,
                },
                {
                    "name": "Test Adaptive B",
                    "minimum_demand": 3,
                    "requirement_qty": 3,
                    "selling_price": 30,
                },
                {
                    "name": "Test Adaptive C",
                    "minimum_demand": 0,
                    "requirement_qty": 2,
                    "selling_price": 10,
                },
            ],
        )
    )

    try:
        data = get_optimization_data(db, cycle.id)

        first = solve_optimization(
            cycle.id,
            data["products"],
            data["cycle_resources"],
            data["requirements"],
        )
        second = solve_optimization(
            cycle.id,
            data["products"],
            data["cycle_resources"],
            data["requirements"],
        )

        first_by_name = {
            a["product_name"]: (a["quantity"], a["shortfall"])
            for a in first["allocations"]
        }
        second_by_name = {
            a["product_name"]: (a["quantity"], a["shortfall"])
            for a in second["allocations"]
        }

        assert first_by_name == second_by_name
        assert first["objective_value"] == second["objective_value"]
    finally:
        _cleanup_single_resource_scenario(
            db, resource, cycle, cycle_resource, products, requirements
        )


def test_rule_g_widened_to_zero_minimum_products(db, optimization_cycle):
    """
    Rule G extension: validate_minimum_demand_resource_availability now
    also rejects a zero-minimum-demand product whose requirement points
    at a resource with no CycleResource row this cycle at all -
    previously only a minimum_demand > 0 product was checked, silently
    dropping this same data-completeness problem for a zero-minimum
    product instead (it would just look "coverable" when it secretly
    wasn't, since get_optimization_data() would drop the unpriced
    requirement without a trace).
    """

    unpriced_resource = Resource(
        name="Test Unpriced Resource For Zero Minimum",
        resource_type="material",
        unit="pcs",
        is_active=True,
    )
    db.add(unpriced_resource)
    db.commit()
    db.refresh(unpriced_resource)

    zero_minimum_product = Product(
        name="Test Zero Minimum Needs Unpriced Resource",
        selling_price=Decimal("100.00"),
        labor_cost=Decimal("0"),
        minimum_demand=Decimal("0"),
        is_active=True,
    )
    db.add(zero_minimum_product)
    db.commit()
    db.refresh(zero_minimum_product)

    # Links this product to the cycle's own priced-resource universe,
    # so the widened check treats it as a genuine coverage candidate -
    # then a SECOND requirement, on unpriced_resource (no CycleResource
    # row this cycle), is the actual thing being tested.
    priced_resource = db.scalar(
        select(Resource)
        .join(CycleResource, CycleResource.resource_id == Resource.id)
        .where(CycleResource.production_cycle_id == optimization_cycle.id)
    )

    bridging_requirement = ProductResourceRequirement(
        product_id=zero_minimum_product.id,
        resource_id=priced_resource.id,
        quantity_required=Decimal("1.0000"),
    )
    unpriced_requirement = ProductResourceRequirement(
        product_id=zero_minimum_product.id,
        resource_id=unpriced_resource.id,
        quantity_required=Decimal("1.0000"),
    )
    db.add(bridging_requirement)
    db.add(unpriced_requirement)
    db.commit()

    try:
        raised = None

        try:
            validate_minimum_demand_resource_availability(
                db, optimization_cycle.id
            )
        except ValueError as exc:
            raised = str(exc)

        assert raised is not None, (
            "expected ValueError for a zero-minimum product needing an "
            "unpriced resource"
        )
        assert "Test Zero Minimum Needs Unpriced Resource" in raised
        assert "Test Unpriced Resource For Zero Minimum" in raised
        assert "eligible for production coverage" in raised
    finally:
        db.delete(bridging_requirement)
        db.delete(unpriced_requirement)
        db.delete(zero_minimum_product)
        db.delete(unpriced_resource)
        db.commit()


def test_adaptive_forecast_absent_entry_has_no_ceiling(db):
    """
    Plan row #24: the router's existing "no key == no ceiling" forecast
    behavior (already covered for Phase 1 by
    test_forecast_absent_entry_has_no_ceiling above) must hold
    identically under genuine Phase 2 routing - forecast=None and
    forecast={} must produce the exact same adaptive result as no
    forecast argument at all, on a scenario that is actually infeasible
    under hard minimums (the same worked example as
    test_adaptive_worked_example_matches_hand_verified_plan, reused
    here specifically to keep both forecast-absent forms on the
    adaptive path rather than the hard-minimum fast path).
    """

    resource, cycle, cycle_resource, products, requirements = (
        _build_single_resource_scenario(
            db,
            resource_unit="units",
            available_quantity=25,
            unit_price=0,
            product_specs=[
                {
                    "name": "Test Adaptive A",
                    "minimum_demand": 5,
                    "requirement_qty": 4,
                    "selling_price": 50,
                },
                {
                    "name": "Test Adaptive B",
                    "minimum_demand": 3,
                    "requirement_qty": 3,
                    "selling_price": 30,
                },
                {
                    "name": "Test Adaptive C",
                    "minimum_demand": 0,
                    "requirement_qty": 2,
                    "selling_price": 10,
                },
            ],
        )
    )

    try:
        data = get_optimization_data(db, cycle.id)

        no_forecast_arg = solve_optimization(
            cycle.id,
            data["products"],
            data["cycle_resources"],
            data["requirements"],
        )
        forecast_none = solve_optimization(
            cycle.id,
            data["products"],
            data["cycle_resources"],
            data["requirements"],
            forecast=None,
        )
        forecast_empty = solve_optimization(
            cycle.id,
            data["products"],
            data["cycle_resources"],
            data["requirements"],
            forecast={},
        )

        def _quantities(result):
            return {
                a["product_name"]: (a["quantity"], a["shortfall"])
                for a in result["allocations"]
            }

        assert no_forecast_arg["status"] == "Optimal"
        assert _quantities(no_forecast_arg) == _quantities(forecast_none)
        assert _quantities(no_forecast_arg) == _quantities(forecast_empty)

        # Matches the hand-verified worked example exactly - confirms
        # neither forecast-absent form silently imposed a hidden cap.
        quantity_by_name = {
            name: qty for name, (qty, _) in _quantities(no_forecast_arg).items()
        }
        assert quantity_by_name["Test Adaptive A"] == 4
        assert quantity_by_name["Test Adaptive B"] == 2
        assert quantity_by_name["Test Adaptive C"] == 1
    finally:
        _cleanup_single_resource_scenario(
            db, resource, cycle, cycle_resource, products, requirements
        )


def test_rule_g_widening_blocks_zero_minimum_product_at_http_level(
    client,
    db,
    optimization_cycle,
    test_products,
    test_resources,
):
    """
    Plan row #25: Rule G's widening is an intentional, documented
    behavior change - a call that previously SUCCEEDED (200) now
    correctly 400s. Test Bed Frame has minimum_demand=0 (the
    test_products fixture never sets it, and the column defaults to 0)
    and is never otherwise modified in this test, so before Rule G
    widened validate_minimum_demand_resource_availability beyond
    `Product.minimum_demand > 0`, deleting its "Test Nails"
    CycleResource row would have gone completely unvalidated (the
    product would have just silently dropped the nails requirement in
    get_optimization_data and been treated as coverable). After the
    widening, this is now a hard, pre-solve 400 - same as the existing
    positive-minimum case in
    test_minimum_demand_blocked_by_unpriced_resource_this_cycle, but
    exercised here for a zero-minimum product specifically, at the real
    HTTP endpoint rather than by calling the validator directly.
    """

    resources_by_name = {r.name: r for r in test_resources}

    bed_frame = next(
        p for p in test_products if p.name == "Test Bed Frame"
    )
    assert bed_frame.minimum_demand == Decimal("0")

    nails_cycle_resource = db.scalar(
        select(CycleResource).where(
            CycleResource.production_cycle_id == optimization_cycle.id,
            CycleResource.resource_id == resources_by_name["Test Nails"].id,
        )
    )
    removed_available = nails_cycle_resource.available_quantity
    removed_price = nails_cycle_resource.unit_price
    db.delete(nails_cycle_resource)
    db.commit()

    try:
        response = client.post(
            f"/api/production-cycles/{optimization_cycle.id}/optimize",
            json={"objective": "MAX_PROFIT"},
        )

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "Test Bed Frame" in detail
        assert "Test Nails" in detail
        assert "eligible for production coverage" in detail
    finally:
        db.add(
            CycleResource(
                production_cycle_id=optimization_cycle.id,
                resource_id=resources_by_name["Test Nails"].id,
                available_quantity=removed_available,
                unit_price=removed_price,
            )
        )
        db.commit()

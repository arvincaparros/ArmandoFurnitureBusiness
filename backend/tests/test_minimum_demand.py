from decimal import Decimal

from sqlalchemy import select

from app.database.models import (
    CycleResource,
    OptimizationResult,
    OptimizationRun,
    Product,
    ProductionAllocation,
    ProductResourceRequirement,
    Resource,
)

from app.services.optimization import (
    create_decision_variables,
    create_shortfall_variables,
    get_optimization_data,
    solve_optimization,
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


# --- B. Decision/shortfall variables (Revision #4) -----------------------


def test_decision_variable_lowbound_is_always_zero(
    db,
    test_products,
):
    """
    Revision #4: minimum_demand is no longer wired in as the ILP
    variable's lowBound - that was the hard constraint that made an
    unreachable minimum block the whole plan. It's every decision
    variable's lowBound now, regardless of minimum_demand.
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

    for product in test_products:
        variable = variables[product.id]
        assert variable.lowBound == 0
        assert variable.cat == "Integer"


def test_shortfall_variables_created_only_for_positive_minimum_demand(
    db,
    test_products,
):
    products_by_name = {p.name: p for p in test_products}

    products_by_name["Test Dining Table"].minimum_demand = Decimal("7")
    products_by_name["Test Chair"].minimum_demand = Decimal("0")
    products_by_name["Test Bed Frame"].minimum_demand = Decimal("3")
    db.commit()

    for product in test_products:
        db.refresh(product)

    shortfall_variables = create_shortfall_variables(test_products)

    dining_table = products_by_name["Test Dining Table"]
    chair = products_by_name["Test Chair"]
    bed_frame = products_by_name["Test Bed Frame"]

    assert dining_table.id in shortfall_variables
    assert bed_frame.id in shortfall_variables
    assert chair.id not in shortfall_variables

    assert shortfall_variables[dining_table.id].lowBound == 0
    assert shortfall_variables[dining_table.id].cat == "Integer"


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
        # All minimums are achievable here - Revision #4 must produce
        # zero shortfall everywhere, identical to the old hard-bound
        # behavior.
        assert shortfall_by_name[product.name] == Decimal("0")

    # Test Dining Table's minimum is 0 - legitimately allowed to stay 0.
    assert quantity_by_name["Test Dining Table"] >= 0

    # The optimizer is free to exceed a minimum when resources/profit
    # allow it - Test Chair's minimum is 2 but nothing caps it there.
    assert quantity_by_name["Test Chair"] >= 2

    # Independently re-verify every resource constraint still holds
    # (Revision #4 must not weaken add_resource_constraints).
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


# --- D. Minimum-capacity shortage: plan still generated (Revision #4) -----


def test_minimum_demand_capacity_shortage_produces_shortfall_not_rejection(
    client,
    db,
    optimization_cycle,
    test_products,
):
    """
    The exact scenario that used to return HTTP 400 with no plan at
    all (validate_minimum_demand_capacity, removed in Revision #4).
    The clarified business requirement: the system must still return
    the best feasible plan, with a shortfall reported for whichever
    product(s) can't reach their minimum - never reject the whole
    plan over it.
    """

    products_by_name = {p.name: p for p in test_products}

    # Test Chair needs 0.5 Epoxy/unit, only 8 Epoxy available -> minimum
    # 20 needs 10 Epoxy, a clean shortage.
    products_by_name["Test Chair"].minimum_demand = Decimal("20")

    # Test Dining Table needs 45 Wood/unit, only 1250 Wood available ->
    # minimum 30 needs 1350 Wood, a second, independent shortage.
    products_by_name["Test Dining Table"].minimum_demand = Decimal("30")

    db.commit()

    runs_before = db.scalar(
        select(OptimizationRun).where(
            OptimizationRun.production_cycle_id == optimization_cycle.id
        )
    )

    response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "OPTIMAL"

    allocations_by_name = {
        a["product_name"]: a for a in data["allocations"]
    }
    chair = allocations_by_name["Test Chair"]
    dining_table = allocations_by_name["Test Dining Table"]

    assert chair["quantity"] < 20
    assert Decimal(str(chair["minimum_demand"])) == Decimal("20")
    assert Decimal(str(chair["shortfall"])) == Decimal("20") - Decimal(
        str(chair["quantity"])
    )

    assert dining_table["quantity"] < 30
    assert Decimal(str(dining_table["minimum_demand"])) == Decimal("30")
    assert Decimal(str(dining_table["shortfall"])) == Decimal(
        "30"
    ) - Decimal(str(dining_table["quantity"]))

    # Resource usage must never exceed availability, even under
    # shortfall.
    for usage in data["resource_usage"]:
        assert Decimal(str(usage["required_quantity"])) <= Decimal(
            str(usage["available_quantity"])
        )

    # An optimization run IS now persisted (unlike the old 400, which
    # never reached save_optimization_history).
    runs_after = db.scalar(
        select(OptimizationRun).where(
            OptimizationRun.production_cycle_id == optimization_cycle.id
        )
    )
    assert runs_after is not None
    if runs_before is not None:
        assert runs_after.id != runs_before.id


# --- E. Forecast below minimum: plan still generated (Revision #4) --------


def test_forecast_below_minimum_produces_shortfall(
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
        forecast={chair.id: Decimal("4")},
    )

    assert result["status"] == "Optimal"

    allocation = next(
        a for a in result["allocations"] if a["product_id"] == chair.id
    )

    # Forecast is the only binding cap here (resources are ample) -
    # the plan is generated, capped at forecast, with the gap to
    # minimum_demand reported as shortfall rather than rejected.
    assert allocation["quantity"] == 4
    assert allocation["minimum_demand"] == Decimal("5")
    assert allocation["shortfall"] == Decimal("1")


def test_forecast_equal_to_minimum_has_no_shortfall(
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


# --- F. Resource lifecycle (Revision #4: inactive -> zero capacity) -------


def test_minimum_demand_inactive_resource_produces_shortfall_not_rejection(
    client,
    db,
    optimization_cycle,
    test_products,
    test_resources,
):
    """
    An inactive resource is now modeled as zero available capacity
    (add_resource_constraints), not a validation error - the affected
    product is pushed toward a minimum-demand shortfall exactly like
    any other capacity shortage, and the plan is still generated.
    """

    products_by_name = {p.name: p for p in test_products}
    resources_by_name = {r.name: r for r in test_resources}

    products_by_name["Test Chair"].minimum_demand = Decimal("1")
    resources_by_name["Test Nails"].is_active = False
    db.commit()

    response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPTIMAL"

    # Every fixture product (Dining Table, Chair, Bed Frame) requires
    # Test Nails, so zeroing its capacity forces all of them to 0 -
    # this is the correct, physically consistent outcome (you cannot
    # produce any of them without a required, now-unavailable input).
    for allocation in data["allocations"]:
        assert allocation["quantity"] == 0

    chair = next(
        a for a in data["allocations"] if a["product_name"] == "Test Chair"
    )
    assert Decimal(str(chair["shortfall"])) == Decimal("1")

    for usage in data["resource_usage"]:
        assert Decimal(str(usage["required_quantity"])) <= Decimal(
            str(usage["available_quantity"])
        )

    # The reported resource_usage must reflect the same zero-capacity
    # treatment the solver actually used - not the resource's stale,
    # pre-deactivation available_quantity (which would make it look
    # like there was unused slack rather than the actual reason every
    # product was forced to 0).
    nails_usage = next(
        usage
        for usage in data["resource_usage"]
        if usage["resource_name"] == "Test Nails"
    )
    assert Decimal(str(nails_usage["available_quantity"])) == Decimal("0")
    assert Decimal(str(nails_usage["remaining_quantity"])) == Decimal("0")


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
    safe to fall back to, so this remains a hard validation error
    (Revision #4 case 3: genuinely missing pricing/cost data must not
    be silently treated as free/unlimited).
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
    products_by_name = {p.name: p for p in test_products}
    resources_by_name = {r.name: r for r in test_resources}

    products_by_name["Test Chair"].minimum_demand = Decimal("1")
    resources_by_name["Test Nails"].is_active = False
    db.commit()

    shortfall_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )
    assert shortfall_response.status_code == 200
    shortfall_data = shortfall_response.json()
    chair_before = next(
        a
        for a in shortfall_data["allocations"]
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


def test_inactive_resource_isolates_shortfall_to_dependent_product(
    db,
    optimization_cycle,
    test_products,
    test_resources,
):
    """
    Distinguishes an inactive resource shared by every product (see
    the "produces_shortfall_not_rejection" test above, where all three
    fixture products depend on Test Nails) from one that only a single
    product depends on - a resource going inactive must not drag down
    products that never used it. Adds an ad-hoc resource used ONLY by
    Test Chair, mirroring test_resource_usage_filtering.py's
    _add_orphan_cycle_resource pattern for constructing one-off
    resources/requirements directly in a test.

    Checked against Test Bed Frame, not Test Dining Table: in this
    fixture's ample-resource baseline (test_optimization.py::
    test_optimization_returns_optimal_solution), Dining Table is
    already the profit-maximizer's choice to produce 0 units with no
    minimum demand and no inactive resource involved at all - it
    wouldn't demonstrate anything here either way. Bed Frame produces
    12 in that same baseline (and even more here, since Chair being
    forced to 0 frees up the Wood/Nails/Labor it would otherwise have
    competed for), making it the right witness for "a product with no
    dependency on the inactive resource keeps being optimized
    normally" - a strict quantity > 0 is what that requires, not an
    exact number that depends on how much Chair's absence frees up.
    """

    products_by_name = {p.name: p for p in test_products}
    chair = products_by_name["Test Chair"]
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

        # Bed Frame has no dependency on the inactive resource at all
        # - it must still be optimized normally (same baseline optimum
        # as without Chair's issue at all), not dragged to 0 by
        # Chair's shortage.
        assert allocations_by_id[bed_frame.id]["quantity"] > 0
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


# --- H. Revision #2 financial reconciliation --------------------------------


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


# --- I. Lexicographic two-stage correctness (Revision #4) -----------------


def test_shortfall_is_minimal_and_profit_is_maximal_among_tied_plans(
    db,
    optimization_cycle,
    test_products,
):
    """
    Hand-verified tie-breaking scenario. Test Chair (unit_profit
    2149.0000) and Test Bed Frame (unit_profit 10332.0000, from the
    same ample-resource baseline as test_optimization_returns_optimal_
    solution in test_optimization.py) both get minimum_demand=6 and
    both require exactly 1 unit of a new zero-priced "Scarce" resource
    per unit produced; only 10 units of Scarce are available (Wood/
    Epoxy/Nails/Labor are all left with ample headroom at these
    quantities, so Scarce is the only binding constraint). Test Dining
    Table is capped at forecast=0 so it can't consume shared resources
    and confound the analysis.

    Since 6 + 6 = 12 > 10, at least 2 units of total shortfall are
    mathematically unavoidable (chair + bed_frame <= 10 while each
    needs 6) - Stage 1 must find total_shortfall == 2. That leaves a
    genuine tie for Stage 2 to break: any (chair, bed_frame) split
    summing to 10 with each <= 6 - e.g. (6, 4), (5, 5), or (4, 6) -
    achieves that same minimal total shortfall of 2. Because Bed
    Frame's unit_profit is far higher, maximizing profit among those
    ties means giving Bed Frame its full minimum (0 shortfall) and
    letting Chair absorb the entire shortfall - the opposite split
    (chair=6, bed_frame=4) would be shortfall-optimal too, but far
    less profitable (54222 vs 70588), so Stage 2 must reject it.
    """

    products_by_name = {p.name: p for p in test_products}
    chair = products_by_name["Test Chair"]
    bed_frame = products_by_name["Test Bed Frame"]
    dining_table = products_by_name["Test Dining Table"]

    chair.minimum_demand = Decimal("6")
    bed_frame.minimum_demand = Decimal("6")
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

        total_shortfall = (
            chair_allocation["shortfall"] + bed_frame_allocation["shortfall"]
        )
        assert total_shortfall == Decimal("2")

        # Profit-maximal among the shortfall-minimal ties: Bed Frame
        # (far more profitable) keeps its full minimum; Chair absorbs
        # the entire unavoidable shortfall.
        assert bed_frame_allocation["quantity"] == 6
        assert bed_frame_allocation["shortfall"] == Decimal("0")
        assert chair_allocation["quantity"] == 4
        assert chair_allocation["shortfall"] == Decimal("2")

        expected_profit = (
            Decimal("4") * Decimal("2149.0000")
            + Decimal("6") * Decimal("10332.0000")
        )
        assert chair_allocation["total_profit"] + bed_frame_allocation[
            "total_profit"
        ] == expected_profit

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

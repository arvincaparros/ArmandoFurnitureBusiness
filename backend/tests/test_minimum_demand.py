from decimal import Decimal

from sqlalchemy import select

from app.database.models import (
    CycleResource,
    OptimizationResult,
    OptimizationRun,
    Product,
    ProductionAllocation,
    Resource,
)

from app.services.optimization import (
    create_decision_variables,
    get_optimization_data,
    solve_optimization,
    validate_minimum_demand_forecast,
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


# --- B. Decision variables ----------------------------------------------


def test_decision_variable_lowbound_comes_from_minimum_demand_not_position(
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

    # Deliberately reversed from DB/insertion order - proves the
    # mapping is keyed by product identity, not list position.
    shuffled = list(reversed(test_products))

    variables = create_decision_variables(shuffled)

    for product in test_products:
        variable = variables[product.id]
        assert variable.lowBound == float(product.minimum_demand)
        assert variable.cat == "Integer"


# --- C. Successful optimization ------------------------------------------


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

    for product in test_products:
        assert quantity_by_name[product.name] >= product.minimum_demand
        assert isinstance(quantity_by_name[product.name], int)

    # Test Dining Table's minimum is 0 - legitimately allowed to stay 0.
    assert quantity_by_name["Test Dining Table"] >= 0

    # The optimizer is free to exceed a minimum when resources/profit
    # allow it - Test Chair's minimum is 2 but nothing caps it there.
    assert quantity_by_name["Test Chair"] >= 2

    # Independently re-verify every resource constraint still holds
    # (Revision #3 must not weaken add_resource_constraints).
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


# --- D. Minimum-capacity failure ------------------------------------------


def test_minimum_demand_capacity_shortage_reports_all_shortages(
    client,
    db,
    optimization_cycle,
    test_products,
):
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

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Epoxy" in detail
    assert "Wood" in detail

    runs_after = db.scalar(
        select(OptimizationRun).where(
            OptimizationRun.production_cycle_id == optimization_cycle.id
        )
    )

    # A failed pre-solve validation must not create/persist any
    # OptimizationRun/OptimizationResult rows.
    assert (runs_before is None) == (runs_after is None)
    if runs_before is not None and runs_after is not None:
        assert runs_before.id == runs_after.id


# --- E. Forecast conflict --------------------------------------------------


def test_forecast_below_minimum_is_rejected(db, test_products):
    products_by_name = {p.name: p for p in test_products}
    chair = products_by_name["Test Chair"]
    chair.minimum_demand = Decimal("5")
    db.commit()
    db.refresh(chair)

    try:
        validate_minimum_demand_forecast(
            test_products,
            {chair.id: Decimal("4")},
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "Test Chair" in str(exc)
        assert "5" in str(exc)
        assert "4" in str(exc)


def test_forecast_equal_to_minimum_is_valid(db, test_products):
    products_by_name = {p.name: p for p in test_products}
    chair = products_by_name["Test Chair"]
    chair.minimum_demand = Decimal("5")
    db.commit()
    db.refresh(chair)

    # Must not raise.
    validate_minimum_demand_forecast(
        test_products,
        {chair.id: Decimal("5")},
    )


def test_forecast_absent_entry_does_not_conflict(db, test_products):
    """
    Matches the router's existing behavior of excluding forecast_quantity
    == 0 entries entirely (production.py::optimize_production) - a
    product with no key in the forecast dict has no ceiling at all
    today, so it can never conflict with its own minimum.
    """

    products_by_name = {p.name: p for p in test_products}
    chair = products_by_name["Test Chair"]
    chair.minimum_demand = Decimal("5")
    db.commit()
    db.refresh(chair)

    validate_minimum_demand_forecast(test_products, {})
    validate_minimum_demand_forecast(test_products, None)


# --- F. Resource lifecycle --------------------------------------------------


def test_minimum_demand_blocked_by_inactive_required_resource(
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

    response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Test Chair" in detail
    assert "Test Nails" in detail
    assert "inactive" in detail


def test_minimum_demand_blocked_by_unpriced_resource_this_cycle(
    client,
    db,
    optimization_cycle,
    test_products,
    test_resources,
):
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

    blocked = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )
    assert blocked.status_code == 400

    resources_by_name["Test Nails"].is_active = True
    db.commit()

    recovered = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )

    assert recovered.status_code == 200
    assert recovered.json()["status"] == "OPTIMAL"


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

    allocations = db.scalars(
        select(ProductionAllocation).where(
            ProductionAllocation.production_cycle_id == optimization_cycle.id
        )
    ).all()

    persisted_by_product_id = {
        allocation.product_id: allocation.quantity
        for allocation in allocations
    }

    chair = products_by_name["Test Chair"]
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

from datetime import datetime
from decimal import Decimal

from app.services.optimization import (
    build_optimization_result,
    calculate_optimized_resource_usage,
    calculate_unit_profit,
    get_optimization_data,
    identify_optimization_bottlenecks,
    solve_optimization,
)

from app.database.models import (
    CycleResource,
    ProductionAllocation,
    ProductionCycle,
    OptimizationResult,
    OptimizationRun,
    Product,
    ProductResourceRequirement,
    Resource,
    SalesTransaction,
)

from app.services.forecasting import get_forecast

def get_test_data(db, optimization_cycle):
    return get_optimization_data(
        db,
        optimization_cycle.id,
    )


def test_optimization_returns_optimal_solution(
    db,
    optimization_cycle,
    test_products,
):
    data = get_test_data(
        db,
        optimization_cycle,
    )

    result = solve_optimization(
        optimization_cycle.id,
        data["products"],
        data["cycle_resources"],
        data["requirements"],
    )

    assert result["status"] == "Optimal"

    allocations = {
        item["product_name"]: item
        for item in result["allocations"]
    }

    dining_table = allocations["Test Dining Table"]
    chair = allocations["Test Chair"]
    bed_frame = allocations["Test Bed Frame"]

    assert dining_table["product_id"] == next(
        product.id
        for product in test_products
        if product.name == "Test Dining Table"
    )
    assert dining_table["quantity"] == 0
    # test_products'/conftest.py labor_cost=0 for all fixture products,
    # and calculate_unit_profit no longer subtracts
    # labor_hours x CycleResource(Labor).unit_price - these figures
    # are 5400/1200/6000 higher than before this change (36/8/40 labor
    # hours x the old 150/hr rate that no longer applies to cost).
    assert dining_table["unit_profit"] == Decimal("8489.0000")
    assert dining_table["total_profit"] == Decimal("0.0000")

    assert chair["product_id"] == next(
        product.id
        for product in test_products
        if product.name == "Test Chair"
    )
    assert chair["quantity"] == 12
    assert chair["unit_profit"] == Decimal("2149.0000")
    assert chair["total_profit"] == Decimal("25788.0000")

    assert bed_frame["product_id"] == next(
        product.id
        for product in test_products
        if product.name == "Test Bed Frame"
    )
    assert bed_frame["quantity"] == 12
    assert bed_frame["unit_profit"] == Decimal("10332.0000")
    assert bed_frame["total_profit"] == Decimal("123984.0000")


def test_optimization_profit(db, optimization_cycle):
    data = get_test_data(
        db,
        optimization_cycle,
    )

    result = solve_optimization(
        optimization_cycle.id,
        data["products"],
        data["cycle_resources"],
        data["requirements"],
    )

    final = build_optimization_result(
        optimization_cycle.id,
        data["products"],
        data["cycle_resources"],
        data["requirements"],
        result["allocations"],
        result["status"],
    )

    assert final["total_revenue"] == Decimal("222000.00")
    assert final["total_cost"] == Decimal("72228.00000000")
    assert final["total_profit"] == Decimal("149772.00000000")


def _make_labor_cost_test_fixtures(db, labor_cost_a, labor_cost_b):
    """
    Self-contained fixtures (not the shared test_resources/
    test_products) so labor hours/BOM can be made IDENTICAL between
    two products - the exact shape needed to prove labor cost is a
    per-product value, not labor_hours x a shared rate. Caller is
    responsible for cleanup (returned objects are added but not
    committed to a cycle).
    """

    wood = Resource(
        name="Labor Cost Test Wood",
        resource_type="material",
        unit="BF",
    )
    labor = Resource(
        name="Labor Cost Test Labor",
        resource_type="labor",
        unit="hours",
    )

    db.add_all([wood, labor])
    db.flush()

    product_a = Product(
        name="Labor Cost Test Product A",
        selling_price=Decimal("3500.00"),
        labor_cost=labor_cost_a,
    )
    product_b = Product(
        name="Labor Cost Test Product B",
        selling_price=Decimal("3500.00"),
        labor_cost=labor_cost_b,
    )

    db.add_all([product_a, product_b])
    db.flush()

    # Identical BOM and identical labor HOURS for both products -
    # only labor_cost differs (see the two callers below).
    requirements = [
        ProductResourceRequirement(
            product_id=product_a.id,
            resource_id=wood.id,
            quantity_required=Decimal("8.0000"),
        ),
        ProductResourceRequirement(
            product_id=product_a.id,
            resource_id=labor.id,
            quantity_required=Decimal("8.0000"),
        ),
        ProductResourceRequirement(
            product_id=product_b.id,
            resource_id=wood.id,
            quantity_required=Decimal("8.0000"),
        ),
        ProductResourceRequirement(
            product_id=product_b.id,
            resource_id=labor.id,
            quantity_required=Decimal("8.0000"),
        ),
    ]

    db.add_all(requirements)
    db.flush()

    cycle_resources = [
        CycleResource(
            resource_id=wood.id,
            available_quantity=Decimal("1250.0000"),
            unit_price=Decimal("84.00"),
        ),
        # Labor's unit_price is deliberately a nonzero, clearly-wrong-
        # if-used value (999/hr) - if calculate_unit_profit ever
        # regresses to costing labor via this rate again, these tests
        # will fail loudly instead of silently passing by coincidence.
        CycleResource(
            resource_id=labor.id,
            available_quantity=Decimal("576.0000"),
            unit_price=Decimal("999.00"),
        ),
    ]

    requirement_rows = [
        (requirement, wood if requirement.resource_id == wood.id else labor)
        for requirement in requirements
    ]

    return product_a, product_b, cycle_resources, requirement_rows, [wood, labor]


def test_labor_cost_is_independent_of_labor_hours(db):
    """
    Mirrors the client reconciliation's decisive proof (High Chair vs
    Ordinary Chair): two products with IDENTICAL labor hours and an
    IDENTICAL BOM must still get different total cost/profit purely
    from Product.labor_cost - confirming labor is never priced as
    hours x a shared CycleResource rate.
    """

    (
        product_a,
        product_b,
        cycle_resources,
        requirements,
        resources,
    ) = _make_labor_cost_test_fixtures(
        db,
        labor_cost_a=Decimal("350.00"),
        labor_cost_b=Decimal("300.00"),
    )

    try:
        profit_a = calculate_unit_profit(
            product_a, requirements, cycle_resources,
        )
        profit_b = calculate_unit_profit(
            product_b, requirements, cycle_resources,
        )

        # Same selling price, same BOM, same hours - the ONLY possible
        # source of a profit difference is labor_cost.
        assert profit_a - profit_b == (
            product_b.labor_cost - product_a.labor_cost
        )
        assert profit_a != profit_b

        # wood cost = 8 x 84.00 = 672.00; labor's 999.00/hr rate must
        # be completely ignored.
        assert profit_a == (
            product_a.selling_price
            - Decimal("672.00")
            - product_a.labor_cost
        )

    finally:
        db.rollback()


def test_zero_labor_cost_does_not_reduce_profit(db):
    """Validation Case: Product.labor_cost = 0 must not reduce cost."""

    (
        product_a,
        _product_b,
        cycle_resources,
        requirements,
        resources,
    ) = _make_labor_cost_test_fixtures(
        db,
        labor_cost_a=Decimal("0.00"),
        labor_cost_b=Decimal("0.00"),
    )

    try:
        profit = calculate_unit_profit(
            product_a, requirements, cycle_resources,
        )

        assert profit == (
            product_a.selling_price - Decimal("672.00")
        )

    finally:
        db.rollback()


def _build_client_reference_resources(db):
    """
    The client's full resource catalog at the exact rates seeded in
    app/database/seed.py::seed_database() (post doorknob/hand-planer
    correction - see the reconciliation report). Shared by the
    per-product reproduction tests below so each one only has to
    define its own BOM.
    """

    resources = {
        "wood": Resource(name="Client Ref Wood", resource_type="material", unit="BF"),
        "epoxy": Resource(name="Client Ref Epoxy", resource_type="material", unit="L"),
        "nails": Resource(name="Client Ref Nails", resource_type="material", unit="kg"),
        "glue": Resource(name="Client Ref Glue", resource_type="material", unit="L"),
        "sandpaper": Resource(name="Client Ref Sandpaper", resource_type="material", unit="pcs"),
        "doorknob": Resource(name="Client Ref Doorknob", resource_type="material", unit="sets"),
        "labor": Resource(name="Client Ref Labor", resource_type="labor", unit="hours"),
        "saw": Resource(name="Client Ref Saw", resource_type="machine", unit="hours"),
        "table_planer": Resource(name="Client Ref Table Planer", resource_type="machine", unit="hours"),
        "hand_planer": Resource(name="Client Ref Hand Planer", resource_type="machine", unit="hours"),
    }

    db.add_all(resources.values())
    db.flush()

    cycle_resources = [
        CycleResource(resource_id=resources["wood"].id, available_quantity=Decimal("1250.0000"), unit_price=Decimal("84.00")),
        CycleResource(resource_id=resources["epoxy"].id, available_quantity=Decimal("8.0000"), unit_price=Decimal("690.00")),
        CycleResource(resource_id=resources["nails"].id, available_quantity=Decimal("100.0000"), unit_price=Decimal("54.00")),
        CycleResource(resource_id=resources["glue"].id, available_quantity=Decimal("12.0000"), unit_price=Decimal("79.00")),
        CycleResource(resource_id=resources["sandpaper"].id, available_quantity=Decimal("100.0000"), unit_price=Decimal("10.00")),
        # Doorknob & Hinge - client's stated ₱300/set directly, NOT
        # weekly_price(300) / availability(13 sets) = ₱23.08. The 13
        # is only the weekly quantity available.
        CycleResource(resource_id=resources["doorknob"].id, available_quantity=Decimal("13.0000"), unit_price=Decimal("300.00")),
        CycleResource(resource_id=resources["labor"].id, available_quantity=Decimal("576.0000"), unit_price=Decimal("0.00")),
        CycleResource(resource_id=resources["saw"].id, available_quantity=Decimal("336.0000"), unit_price=Decimal("31.57")),
        CycleResource(resource_id=resources["table_planer"].id, available_quantity=Decimal("96.0000"), unit_price=Decimal("31.57")),
        # Hand Planer - exactly half the Saw/Table Planer rate
        # (₱31.56912/hr / 2 = ₱15.78456/hr, rounded to ₱15.78), NOT
        # weekly_price(757.66) / availability(240) = ₱3.16. That
        # naive per-machine derivation was the actual root cause of an
        # earlier ~₱12.62/~₱6.31 per-product discrepancy - solved
        # exactly via the 3 distinct machine-hour profiles across all
        # 11 client products (see the reconciliation report).
        CycleResource(resource_id=resources["hand_planer"].id, available_quantity=Decimal("240.0000"), unit_price=Decimal("15.78")),
    ]

    return resources, cycle_resources


def _add_client_reference_product(db, resources, name, selling_price, labor_cost, bom):
    """
    bom: dict of resource-key -> quantity (Decimal-able). Returns
    (product, requirements) in the (requirement, resource) tuple shape
    calculate_unit_profit expects.
    """

    product = Product(
        name=name,
        selling_price=selling_price,
        labor_cost=labor_cost,
    )
    db.add(product)
    db.flush()

    requirement_models = [
        ProductResourceRequirement(
            product_id=product.id,
            resource_id=resources[key].id,
            quantity_required=Decimal(quantity),
        )
        for key, quantity in bom.items()
    ]
    db.add_all(requirement_models)
    db.flush()

    requirements = [
        (requirement, resources[key])
        for requirement, key in zip(requirement_models, bom.keys())
    ]

    return product, requirements


def test_product_cost_reproduces_client_reference_ordinary_chair(db):
    """
    End-to-end reproduction of the client spreadsheet's x11 (Ordinary
    Chair) using the corrected seed rates from
    app/database/seed.py::seed_database(). Expected total cost/profit
    below are computed from those same centavo-rounded rates (see the
    reconciliation report) - at most a couple of centavos off the
    spreadsheet's own higher-precision 1182.09192/2317.90808 figures,
    which is expected given CycleResource.unit_price is Numeric(12, 2)
    and 15.78 (Hand Planer) is itself a rounding of 15.78456.
    """

    resources, cycle_resources = _build_client_reference_resources(db)

    product, requirements = _add_client_reference_product(
        db, resources,
        name="Client Ref Ordinary Chair",
        selling_price=Decimal("3500.00"),
        labor_cost=Decimal("300.00"),
        bom={
            "wood": "8.0000", "epoxy": "0.1000", "nails": "0.0500",
            "glue": "0.1000", "sandpaper": "2.0000", "labor": "8.0000",
            "saw": "2.0000", "table_planer": "1.0000", "hand_planer": "1.0000",
        },
    )

    try:
        unit_profit = calculate_unit_profit(
            product, requirements, cycle_resources,
        )

        total_cost = product.selling_price - unit_profit

        # material = 8*84 + 0.1*690 + 0.05*54 + 0.1*79 + 2*10 = 771.60
        # machine  = 2*31.57 + 1*31.57 + 1*15.78 = 110.49
        # total    = 771.60 + 110.49 + 300 (labor_cost) = 1182.09
        assert total_cost == Decimal("1182.0900")
        assert unit_profit == Decimal("2317.9100")

    finally:
        db.rollback()


def test_product_cost_reproduces_client_reference_doors(db):
    """
    End-to-end reproduction of all four client Door products (x6-x9) -
    the products the incorrect ₱23.08/set doorknob rate affected most
    (a ₱1/set requirement is a much bigger share of a door's BOM than
    of a table's). Expected values are computed from the corrected
    seed rates (doorknob ₱300/set, hand planer ₱15.78/hr) and match
    the client's reference figures to within a few centavos - the
    residual expected from CycleResource.unit_price being
    Numeric(12, 2) (see the reconciliation report), not the ~₱283
    gap the incorrect doorknob rate previously produced.
    """

    resources, cycle_resources = _build_client_reference_resources(db)

    # (name, wood_bf, selling_price, ref_total_cost, ref_profit)
    doors = [
        ("Door (60x210)", "22.0000", Decimal("3800.00"), Decimal("2913.63"), Decimal("886.37")),
        ("Door (70x210)", "25.0000", Decimal("3800.00"), Decimal("3165.63"), Decimal("634.37")),
        ("Door (80x210)", "28.0000", Decimal("3800.00"), Decimal("3417.63"), Decimal("382.37")),
        ("Door (90x210)", "30.0000", Decimal("3800.00"), Decimal("3585.63"), Decimal("214.37")),
    ]

    try:
        for name, wood_bf, selling_price, ref_total_cost, ref_profit in doors:
            product, requirements = _add_client_reference_product(
                db, resources,
                name=f"Client Ref {name}",
                selling_price=selling_price,
                labor_cost=Decimal("500.00"),
                bom={
                    "wood": wood_bf, "epoxy": "0.2000", "nails": "0.2000",
                    "glue": "0.2000", "sandpaper": "3.0000", "doorknob": "1.0000",
                    "labor": "8.0000", "saw": "1.0000", "table_planer": "1.0000",
                    "hand_planer": "0.5000",
                },
            )

            unit_profit = calculate_unit_profit(
                product, requirements, cycle_resources,
            )
            total_cost = product.selling_price - unit_profit

            # Within 1 centavo of the client's reference figures - was
            # off by ~₱283 before the doorknob correction.
            assert abs(total_cost - ref_total_cost) <= Decimal("0.01")
            assert abs(unit_profit - ref_profit) <= Decimal("0.01")

    finally:
        db.rollback()


def test_optimized_resource_usage(db, optimization_cycle, test_resources):
    data = get_test_data(
        db,
        optimization_cycle,
    )

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

    labor_resource = next(
        resource
        for resource in test_resources
        if resource.name == "Test Labor"
    )

    labor = next(
        item
        for item in usage
        if item["resource_id"] == labor_resource.id
    )

    assert labor["required_quantity"] == Decimal("576.0000")
    assert labor["available_quantity"] == Decimal("576.0000")
    assert labor["remaining_quantity"] == Decimal("0.0000")


def test_optimization_bottleneck(db, optimization_cycle, test_resources):
    data = get_test_data(
        db,
        optimization_cycle,
    )

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

    bottlenecks = identify_optimization_bottlenecks(
        usage
    )

    assert len(bottlenecks) == 1

    bottleneck = bottlenecks[0]

    labor_resource = next(
        resource
        for resource in test_resources
        if resource.name == "Test Labor"
    )

    assert bottleneck["resource_id"] == labor_resource.id
    assert bottleneck["resource_name"] == "Test Labor"
    assert bottleneck["is_binding"] is True
    assert bottleneck["remaining_quantity"] == Decimal("0.0000")

def test_optimize_production_api(client, optimization_cycle):
    response = client.post(
    f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={
            "objective": "MAX_PROFIT",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["cycle_id"] == optimization_cycle.id
    assert data["status"] == "OPTIMAL"
    assert data["objective"] == "MAX_PROFIT"

    assert data["total_revenue"] == "222000.00"
    assert data["total_profit"] == "149772.00000000"

    allocations = data["allocations"]

    chair = next(
        item
        for item in allocations
        if item["product_name"] == "Test Chair"
    )

    bed_frame = next(
        item
        for item in allocations
        if item["product_name"] == "Test Bed Frame"
    )

    assert chair["quantity"] == 12
    assert bed_frame["quantity"] == 12

def test_optimize_missing_cycle(client):
    response = client.post(
        "/api/production-cycles/999/optimize",
        json={
            "objective": "MAX_PROFIT",
        },
    )

    assert response.status_code == 404

    data = response.json()

    assert data["detail"] == "Production cycle not found"

def test_zero_resources_returns_zero_production(
    db,
    optimization_cycle,
):
    data = get_test_data(
        db,
        optimization_cycle,
    )

    db.query(CycleResource).filter(
        CycleResource.production_cycle_id
        == optimization_cycle.id
    ).update(
        {
            CycleResource.available_quantity: Decimal("0"),
        },
        synchronize_session=False,
    )

    db.commit()

    data = get_test_data(
        db,
        optimization_cycle,
    )

    result = solve_optimization(
        optimization_cycle.id,
        data["products"],
        data["cycle_resources"],
        data["requirements"],
    )

    assert result["status"] == "Optimal"

    for allocation in result["allocations"]:
        assert allocation["quantity"] == 0
        assert allocation["total_profit"] == Decimal("0.0000")

def test_empty_production_cycle_has_no_resources(db):
    cycle = ProductionCycle(
        cycle_date=datetime(2026, 8, 9),
        start_date=datetime(2026, 8, 9),
        end_date=datetime(2026, 8, 9),
        status="PLANNED",
    )

    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    try:
        data = get_optimization_data(
            db,
            cycle.id,
        )

        forecast_data = get_forecast(db)

        forecast = {
            item["product_id"]: item["forecast_quantity"]
            for item in forecast_data["products"]
            if item["forecast_quantity"] > 0
        }

        assert data["cycle_resources"] == []
        assert data["products"] == []
        assert data["requirements"] == []

    finally:
        db.delete(cycle)
        db.commit()

def test_apply_optimization_api(client, optimization_cycle):
    optimize_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={
            "objective": "MAX_PROFIT",
        },
    )

    assert optimize_response.status_code == 200

    response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["cycle_id"] == optimization_cycle.id
    assert data["status"] == "OPTIMAL"
    assert data["total_profit"] == "149772.00000000"

    allocations = data["allocations"]

    chair = next(
        item
        for item in allocations
        if item["product_name"] == "Test Chair"
    )

    bed_frame = next(
        item
        for item in allocations
        if item["product_name"] == "Test Bed Frame"
    )

    assert chair["quantity"] == 12
    assert bed_frame["quantity"] == 12

def test_optimize_and_apply_return_same_result(
    client,
    optimization_cycle,
):
    optimize_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={
            "objective": "MAX_PROFIT",
        },
    )

    assert optimize_response.status_code == 200

    optimize_data = optimize_response.json()

    apply_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply",
    )

    assert apply_response.status_code == 200

    apply_data = apply_response.json()

    assert apply_data["cycle_id"] == optimize_data["cycle_id"]
    assert apply_data["status"] == optimize_data["status"]
    assert apply_data["objective"] == optimize_data["objective"]

    assert apply_data["total_revenue"] == (
        optimize_data["total_revenue"]
    )

    assert apply_data["total_cost"] == (
        optimize_data["total_cost"]
    )

    assert apply_data["total_profit"] == (
        optimize_data["total_profit"]
    )

    assert apply_data["allocations"] == (
        optimize_data["allocations"]
    )

    assert apply_data["resource_usage"] == (
        optimize_data["resource_usage"]
    )

    assert apply_data["bottlenecks"] == (
        optimize_data["bottlenecks"]
    )

def test_apply_optimization_saves_allocations(
    db,
    client,
    optimization_cycle,
    test_products,
):
    optimize_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={
            "objective": "MAX_PROFIT",
        },
    )

    assert optimize_response.status_code == 200

    response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply",
    )

    assert response.status_code == 200

    allocations = (
        db.query(ProductionAllocation)
        .filter(
            ProductionAllocation.production_cycle_id
            == optimization_cycle.id
        )
        .order_by(
            ProductionAllocation.product_id
        )
        .all()
    )

    products = {
        product.name: product
        for product in test_products
    }

    assert len(allocations) == 2

    assert allocations[0].product_id == products[
        "Test Chair"
    ].id

    assert allocations[0].quantity == Decimal("12.0000")

    assert allocations[1].product_id == products[
        "Test Bed Frame"
    ].id

    assert allocations[1].quantity == Decimal("12.0000")

def test_apply_optimization_is_repeatable(
    db,
    client,
    optimization_cycle,
    test_products,
):
    optimize_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={
            "objective": "MAX_PROFIT",
        },
    )

    assert optimize_response.status_code == 200

    first_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply",
    )

    assert first_response.status_code == 200

    second_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply",
    )

    assert second_response.status_code == 200

    allocations = (
        db.query(ProductionAllocation)
        .filter(
            ProductionAllocation.production_cycle_id == optimization_cycle.id

        )
        .order_by(
            ProductionAllocation.product_id
        )
        .all()
    )

    products = {
        product.name: product
        for product in test_products
    }

    assert len(allocations) == 2

    assert allocations[0].product_id == products[
        "Test Chair"
    ].id
    assert allocations[0].quantity == Decimal("12.0000")

    assert allocations[1].product_id == products[
        "Test Bed Frame"
    ].id
    assert allocations[1].quantity == Decimal("12.0000")


def test_optimize_invalid_objective(client, optimization_cycle):
    response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={
            "objective": "INVALID",
        },
    )

    assert response.status_code == 422

def test_optimization_rejects_unsupported_objective(db, optimization_cycle):
    data = get_test_data(
        db,
        optimization_cycle,
    )

    try:
        solve_optimization(
            optimization_cycle.id,
            data["products"],
            data["cycle_resources"],
            data["requirements"],
            "MIN_COST",
        )

        assert False, "Expected unsupported objective to raise ValueError"

    except ValueError as exc:
        assert str(exc) == (
            "Unsupported optimization objective: MIN_COST"
        )

def test_apply_optimization_missing_cycle(client):
    response = client.post(
        "/api/production-cycles/999/optimize/apply",
    )

    assert response.status_code == 404

    data = response.json()

    assert data["detail"] == "Production cycle not found"

def test_optimize_empty_production_cycle_returns_400(client, db):
    cycle_id = None

    try:
        cycle = ProductionCycle(
            cycle_date=datetime(2026, 8, 9),
            start_date=datetime(2026, 8, 9),
            end_date=datetime(2026, 8, 9),
            status="PLANNED",
        )

        db.add(cycle)
        db.commit()
        db.refresh(cycle)

        cycle_id = cycle.id

        response = client.post(
            f"/api/production-cycles/{cycle_id}/optimize",
            json={
                "objective": "MAX_PROFIT",
            },
        )

        assert response.status_code == 400

        data = response.json()

        assert data["detail"] == (
            "Production cycle has no resources configured"
        )

    finally:
        if cycle_id is not None:
            db.query(ProductionAllocation).filter(
                ProductionAllocation.production_cycle_id == cycle_id
            ).delete(
                synchronize_session=False
            )

            db.query(ProductionCycle).filter(
                ProductionCycle.id == cycle_id
            ).delete(
                synchronize_session=False
            )

            db.commit()


def test_optimize_does_not_modify_allocations(client, db, optimization_cycle):

    before = (
        db.query(ProductionAllocation)
        .filter(
            ProductionAllocation.production_cycle_id == optimization_cycle.id
        )
        .order_by(
            ProductionAllocation.product_id
        )
        .all()
    )

    before_values = [
        (
            allocation.product_id,
            allocation.quantity,
        )
        for allocation in before
    ]

    response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={
            "objective": "MAX_PROFIT",
        },
    )

    assert response.status_code == 200

    after = (
        db.query(ProductionAllocation)
        .filter(
            ProductionAllocation.production_cycle_id == optimization_cycle.id
        )
        .order_by(
            ProductionAllocation.product_id
        )
        .all()
    )

    after_values = [
        (
            allocation.product_id,
            allocation.quantity,
        )
        for allocation in after
    ]

    assert after_values == before_values

def test_apply_optimization_empty_production_cycle_returns_400(
    client,
    db,
):
    cycle = ProductionCycle(
        cycle_date=datetime(2026, 8, 9),
        start_date=datetime(2026, 8, 9),
        end_date=datetime(2026, 8, 9),
        status="PLANNED",
    )

    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    cycle_id = cycle.id

    try:
        response = client.post(
            f"/api/production-cycles/{cycle_id}/optimize/apply",
        )

        assert response.status_code == 400

        data = response.json()

        assert data["detail"] == (
            "Production cycle has no resources configured"
        )

    finally:
        db.delete(cycle)
        db.commit()

def test_optimization_history_models(
    db,
    optimization_cycle,
):
    product = (
        db.query(Product)
        .filter(Product.is_active.is_(True))
        .order_by(Product.id)
        .first()
    )

    assert product is not None

    started_at = datetime.now()
    completed_at = datetime.now()

    optimization_run = OptimizationRun(
        production_cycle_id=optimization_cycle.id,
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=125,
        status="OPTIMAL",
        objective_value=Decimal("63372.0000"),
        total_profit=Decimal("63372.0000"),
    )

    db.add(optimization_run)
    db.commit()
    db.refresh(optimization_run)

    optimization_result = OptimizationResult(
        optimization_run_id=optimization_run.id,
        product_id=product.id,
        recommended_quantity=Decimal("12.0000"),
        unit_profit=Decimal("5281.0000"),
        total_profit=Decimal("63372.0000"),
    )

    db.add(optimization_result)
    db.commit()
    db.refresh(optimization_result)

    assert optimization_run.id is not None
    assert optimization_result.id is not None

    assert optimization_result.optimization_run_id == (
        optimization_run.id
    )

    assert optimization_result.product_id == product.id

    assert optimization_run.results[0].id == (
        optimization_result.id
    )

    assert optimization_result.product.id == product.id

def test_save_optimization_history(
    db,
    optimization_cycle,
):
    from datetime import datetime

    from app.services.optimization_history import (
        save_optimization_history,
    )

    started_at = datetime(2026, 8, 10, 10, 0, 0)
    completed_at = datetime(2026, 8, 10, 10, 0, 0, 125000)

    result = {
        "status": "Optimal",
        "objective_value": 63372.0,
        "allocations": [
            {
                "product_id": 1,
                "product_name": "Test Chair",
                "quantity": 12,
                "unit_profit": Decimal("5281.0000"),
                "total_profit": Decimal("63372.0000"),
            },
        ],
    }

    optimization_run = save_optimization_history(
        db=db,
        cycle_id=optimization_cycle.id,
        started_at=started_at,
        completed_at=completed_at,
        result=result,
    )

    assert optimization_run.id is not None
    assert optimization_run.production_cycle_id == (
        optimization_cycle.id
    )

    assert optimization_run.status == "OPTIMAL"

    assert optimization_run.duration_ms == 125

    assert optimization_run.total_profit == (
        Decimal("63372.0000")
    )

    assert optimization_run.objective_value == (
        Decimal("63372.0000")
    )

    assert len(optimization_run.results) == 1

    history_result = optimization_run.results[0]

    assert history_result.product_id == 1
    assert history_result.recommended_quantity == (
        Decimal("12.0000")
    )

    assert history_result.unit_profit == (
        Decimal("5281.0000")
    )

    assert history_result.total_profit == (
        Decimal("63372.0000")
    )

def test_optimize_saves_optimization_history(
    client,
    db,
    optimization_cycle,
):
    response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={
            "objective": "MAX_PROFIT",
        },
    )

    assert response.status_code == 200

    data = response.json()

    runs = (
        db.query(OptimizationRun)
        .filter(
            OptimizationRun.production_cycle_id
            == optimization_cycle.id
        )
        .all()
    )

    assert len(runs) == 1

    optimization_run = runs[0]

    assert optimization_run.status == "OPTIMAL"

    assert optimization_run.production_cycle_id == (
        optimization_cycle.id
    )

    assert optimization_run.started_at is not None
    assert optimization_run.completed_at is not None
    assert optimization_run.duration_ms is not None

    assert optimization_run.objective_value == (
        Decimal("149772.0000")
    )

    assert optimization_run.total_profit == (
        Decimal("149772.0000")
    )

    assert len(optimization_run.results) == 3

    result_by_product = {
        result.product_id: result
        for result in optimization_run.results
    }

    for allocation in data["allocations"]:
        history_result = result_by_product[
            allocation["product_id"]
        ]

        assert history_result.recommended_quantity == (
            Decimal(str(allocation["quantity"]))
        )

        assert history_result.unit_profit == (
            Decimal(str(allocation["unit_profit"]))
        )

        assert history_result.total_profit == (
            Decimal(str(allocation["total_profit"]))
        )

def test_get_optimization_history(
    client,
    optimization_cycle,
):
    response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={
            "objective": "MAX_PROFIT",
        },
    )

    assert response.status_code == 200

    response = client.get(
        "/api/optimization/history"
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    history = data[0]

    assert history["production_cycle_id"] == (
        optimization_cycle.id
    )

    assert history["status"] == "OPTIMAL"

    assert history["objective_value"] == "149772.0000"

    assert history["total_profit"] == "149772.0000"

    assert len(history["results"]) == 3

def test_get_optimization_history_by_cycle(
    client,
    optimization_cycle,
):
    response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={
            "objective": "MAX_PROFIT",
        },
    )

    assert response.status_code == 200

    response = client.get(
        "/api/optimization/history",
        params={
            "cycle_id": optimization_cycle.id,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    assert data[0]["production_cycle_id"] == (
        optimization_cycle.id
    )

def test_get_optimization_history_detail(
    client,
    optimization_cycle,
):
    response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={
            "objective": "MAX_PROFIT",
        },
    )

    assert response.status_code == 200

    response = client.get(
        "/api/optimization/history"
    )

    assert response.status_code == 200

    history = response.json()[0]

    run_id = history["id"]

    response = client.get(
        f"/api/optimization/history/{run_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == run_id
    assert data["production_cycle_id"] == (
        optimization_cycle.id
    )

    assert data["status"] == "OPTIMAL"
    assert len(data["results"]) == 3

def test_get_optimization_history_detail_not_found(
    client,
):
    response = client.get(
        "/api/optimization/history/999999"
    )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "Optimization run not found"
    )

def test_apply_optimization_without_history_returns_400(
    client,
    optimization_cycle,
):
    response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply",
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "No optimization result found for production cycle."
    )

def test_multiple_optimization_runs_are_preserved(
    db,
    client,
    optimization_cycle,
):
    first_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={
            "objective": "MAX_PROFIT",
        },
    )

    assert first_response.status_code == 200

    second_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={
            "objective": "MAX_PROFIT",
        },
    )

    assert second_response.status_code == 200

    runs = (
        db.query(OptimizationRun)
        .filter(
            OptimizationRun.production_cycle_id
            == optimization_cycle.id
        )
        .order_by(OptimizationRun.id)
        .all()
    )

    assert len(runs) == 2

    assert runs[0].id < runs[1].id

    assert runs[0].status == "OPTIMAL"
    assert runs[1].status == "OPTIMAL"

    assert len(runs[0].results) == 3
    assert len(runs[1].results) == 3

def test_apply_optimization_does_not_create_new_history(
    db,
    client,
    optimization_cycle,
):
    optimize_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={
            "objective": "MAX_PROFIT",
        },
    )

    assert optimize_response.status_code == 200

    runs_before = (
        db.query(OptimizationRun)
        .filter(
            OptimizationRun.production_cycle_id
            == optimization_cycle.id
        )
        .count()
    )

    assert runs_before == 1

    apply_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply",
    )

    assert apply_response.status_code == 200

    runs_after = (
        db.query(OptimizationRun)
        .filter(
            OptimizationRun.production_cycle_id
            == optimization_cycle.id
        )
        .count()
    )

    assert runs_after == 1

def test_apply_optimization_uses_latest_history(
    db,
    client,
    optimization_cycle,
):
    first_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={
            "objective": "MAX_PROFIT",
        },
    )

    assert first_response.status_code == 200

    second_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={
            "objective": "MAX_PROFIT",
        },
    )

    assert second_response.status_code == 200

    runs = (
        db.query(OptimizationRun)
        .filter(
            OptimizationRun.production_cycle_id
            == optimization_cycle.id
        )
        .order_by(OptimizationRun.id)
        .all()
    )

    assert len(runs) == 2

    latest_run = runs[-1]

    assert len(latest_run.results) > 0

    result_to_modify = latest_run.results[0]

    product_id = result_to_modify.product_id

    result_to_modify.recommended_quantity = Decimal(
        "10.0000"
    )

    db.commit()

    response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply",
    )

    assert response.status_code == 200

    allocations = (
        db.query(ProductionAllocation)
        .filter(
            ProductionAllocation.production_cycle_id
            == optimization_cycle.id
        )
        .all()
    )

    applied_allocation = next(
        allocation
        for allocation in allocations
        if allocation.product_id == product_id
    )

    assert applied_allocation.quantity == Decimal(
        "10.0000"
    )

def test_older_optimization_history_is_preserved(
    db,
    client,
    optimization_cycle,
):
    first_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={
            "objective": "MAX_PROFIT",
        },
    )

    assert first_response.status_code == 200

    first_run = (
        db.query(OptimizationRun)
        .filter(
            OptimizationRun.production_cycle_id
            == optimization_cycle.id
        )
        .order_by(OptimizationRun.id.desc())
        .first()
    )

    first_run_id = first_run.id

    first_profit = first_run.total_profit

    second_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={
            "objective": "MAX_PROFIT",
        },
    )

    assert second_response.status_code == 200

    db.expire_all()

    old_run = (
        db.query(OptimizationRun)
        .filter(
            OptimizationRun.id == first_run_id
        )
        .first()
    )

    assert old_run is not None
    assert old_run.total_profit == first_profit
    assert old_run.status == "OPTIMAL"
    assert len(old_run.results) == 3

def test_optimization_respects_forecast_limit(
    db,
    optimization_cycle,
    test_products,
):
    data = get_test_data(
        db,
        optimization_cycle,
    )

    forecast = {
        test_products[1].id: Decimal("5.0000"),
        test_products[2].id: Decimal("5.0000"),
    }

    result = solve_optimization(
        optimization_cycle.id,
        data["products"],
        data["cycle_resources"],
        data["requirements"],
        forecast=forecast,
    )

    assert result["status"] == "Optimal"

    allocations = {
        item["product_id"]: item["quantity"]
        for item in result["allocations"]
    }

    assert allocations[test_products[1].id] <= 5
    assert allocations[test_products[2].id] <= 5

def test_optimize_production_respects_forecast(
    client,
    db,
    optimization_cycle,
    test_products,
):
    historical_transactions = [
        SalesTransaction(
            transaction_number="TRX-OPT-001",
            product_id=test_products[1].id,
            transaction_date=datetime(2026, 8, 9, 10, 0),
            quantity_produced=Decimal("5.0000"),
            quantity=Decimal("5.0000"),
            unit_price=Decimal("3500.00"),
            total_sales=Decimal("17500.00"),
            production_cost=Decimal("12755.0000"),
            unit_profit=Decimal("949.0000"),
            total_profit=Decimal("4745.0000"),
        ),
        SalesTransaction(
            transaction_number="TRX-OPT-002",
            product_id=test_products[2].id,
            transaction_date=datetime(2026, 8, 9, 10, 0),
            quantity_produced=Decimal("5.0000"),
            quantity=Decimal("5.0000"),
            unit_price=Decimal("3500.00"),
            total_sales=Decimal("17500.00"),
            production_cost=Decimal("12755.0000"),
            unit_profit=Decimal("949.0000"),
            total_profit=Decimal("4745.0000"),
        ),
    ]

    db.add_all(historical_transactions)
    db.commit()

    try:
        response = client.post(
            f"/api/production-cycles/{optimization_cycle.id}/optimize",
            json={
                "objective": "MAX_PROFIT",
            },
        )

        assert response.status_code == 200

        data = response.json()

        allocations = {
            item["product_id"]: item["quantity"]
            for item in data["allocations"]
        }

        assert allocations[test_products[1].id] <= 5
        assert allocations[test_products[2].id] <= 5

    finally:
        for allocation in historical_transactions:
            db.delete(allocation)

        db.commit()
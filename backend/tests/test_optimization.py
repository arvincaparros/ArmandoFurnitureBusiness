from decimal import Decimal

from datetime import datetime

from app.services.optimization import (
    build_optimization_result,
    calculate_optimized_resource_usage,
    get_optimization_data,
    identify_optimization_bottlenecks,
    solve_optimization,
)

from app.database.models import (
    CycleResource,
    ProductionAllocation,
    ProductionCycle,
)


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
    assert dining_table["unit_profit"] == Decimal("3089.0000")
    assert dining_table["total_profit"] == Decimal("0.0000")

    assert chair["product_id"] == next(
        product.id
        for product in test_products
        if product.name == "Test Chair"
    )
    assert chair["quantity"] == 12
    assert chair["unit_profit"] == Decimal("949.0000")
    assert chair["total_profit"] == Decimal("11388.0000")

    assert bed_frame["product_id"] == next(
        product.id
        for product in test_products
        if product.name == "Test Bed Frame"
    )
    assert bed_frame["quantity"] == 12
    assert bed_frame["unit_profit"] == Decimal("4332.0000")
    assert bed_frame["total_profit"] == Decimal("51984.0000")


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
    assert final["total_cost"] == Decimal("158628.00000000")
    assert final["total_profit"] == Decimal("63372.00000000")


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
    assert data["total_profit"] == "63372.00000000"

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

        assert data["cycle_resources"] == []
        assert data["products"] == []
        assert data["requirements"] == []

    finally:
        db.delete(cycle)
        db.commit()

def test_apply_optimization_api(client, optimization_cycle):
    response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["cycle_id"] == optimization_cycle.id
    assert data["status"] == "OPTIMAL"
    assert data["total_profit"] == "63372.00000000"

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
    
def test_apply_optimization_saves_allocations(db, client, optimization_cycle, test_products):
    response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply",
    )

    assert response.status_code == 200

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

def test_apply_optimization_is_repeatable(db, client, optimization_cycle, test_products):
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


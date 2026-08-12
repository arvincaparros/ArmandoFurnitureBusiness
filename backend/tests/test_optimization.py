from datetime import datetime
from decimal import Decimal

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
    OptimizationResult,
    OptimizationRun,
    Product,
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
        Decimal("63372.0000")
    )

    assert optimization_run.total_profit == (
        Decimal("63372.0000")
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

    assert history["objective_value"] == "63372.0000"

    assert history["total_profit"] == "63372.0000"

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
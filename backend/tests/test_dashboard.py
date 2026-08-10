from decimal import Decimal

from app.database.models import (
    OptimizationRun,
    ProductionAllocation,
)


def test_dashboard_summary_with_test_data(
    client,
    db,
    optimization_cycle,
    test_products,
):
    response = client.get(
        "/api/dashboard/summary"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_products"] >= 3
    assert data["total_resources"] >= 4
    assert data["total_production_cycles"] >= 1


def test_dashboard_summary_counts_allocations(
    client,
    db,
    optimization_cycle,
    test_products,
):
    allocation = ProductionAllocation(
        production_cycle_id=optimization_cycle.id,
        product_id=test_products[1].id,
        quantity=Decimal("12.0000"),
    )

    db.add(allocation)
    db.commit()

    try:
        response = client.get(
            "/api/dashboard/summary"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["total_allocations"] >= 1

    finally:
        db.delete(allocation)
        db.commit()

def test_dashboard_summary_latest_optimization(
    client,
    db,
    optimization_cycle,
):
    optimize_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={
            "objective": "MAX_PROFIT",
        },
    )

    assert optimize_response.status_code == 200

    response = client.get(
        "/api/dashboard/summary"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_optimization_runs"] >= 1
    assert data["latest_optimization_profit"] is not None
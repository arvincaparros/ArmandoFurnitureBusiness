from datetime import datetime
from decimal import Decimal

from app.database.models import (
    OptimizationRun,
    ProductionAllocation,
)

from app.database.models import SalesTransaction


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

def test_dashboard_summary_sales_totals(
    client,
    db,
    test_products,
):
    transactions = [
        SalesTransaction(
            transaction_number="TRX-TEST-001",
            quantity_produced=Decimal("2.0000"),
            production_cost=Decimal("2551.0000"),
            product_id=test_products[0].id,
            transaction_date=datetime(2026, 8, 10, 10, 0),
            quantity=Decimal("2.0000"),
            unit_price=Decimal("3500.00"),
            total_sales=Decimal("7000.00"),
            unit_profit=Decimal("949.0000"),
            total_profit=Decimal("1898.0000"),
        ),
        SalesTransaction(
            transaction_number="TRX-TEST-002",
            quantity_produced=Decimal("2.0000"),
            production_cost=Decimal("2551.0000"),
            product_id=test_products[1].id,
            transaction_date=datetime(2026, 8, 10, 11, 0),
            quantity=Decimal("3.0000"),
            unit_price=Decimal("5000.00"),
            total_sales=Decimal("15000.00"),
            unit_profit=Decimal("1200.0000"),
            total_profit=Decimal("3600.0000"),
        ),
    ]

    db.add_all(transactions)
    db.commit()

    try:
        response = client.get("/api/dashboard/summary")

        assert response.status_code == 200

        data = response.json()

        assert Decimal(data["total_sales"]) == Decimal("22000.00")
        assert Decimal(data["total_sales_profit"]) == Decimal("5498.0000")

    finally:
        for transaction in transactions:
            db.delete(transaction)

        db.commit()

def test_dashboard_summary_latest_forecast(
    client,
    db,
):
    from app.services.forecast_history import (
        save_forecast_history,
    )
    from app.services.forecasting import get_forecast

    forecast = get_forecast(db)
    run = save_forecast_history(db, forecast)

    try:
        response = client.get("/api/dashboard/summary")

        assert response.status_code == 200

        data = response.json()

        assert data["latest_forecast_period"] == (
            "NEXT_CYCLE"
        )

        assert data["latest_forecast_created_at"] is not None

        expected_total = sum(
            item["forecast_quantity"]
            for item in forecast["products"]
        )

        assert Decimal(
            data["latest_forecast_total_quantity"]
        ) == expected_total

    finally:
        db.delete(run)
        db.commit()
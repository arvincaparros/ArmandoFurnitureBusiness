
from datetime import datetime
from decimal import Decimal

from app.database.models import SalesTransaction


def test_forecast_returns_active_products(
    client,
    optimization_cycle,
    test_products,
):
    response = client.get("/api/forecast")

    assert response.status_code == 200

    data = response.json()

    assert data["forecast_period"] == "NEXT_CYCLE"

    products = {
        item["product_name"]: item
        for item in data["products"]
    }

    assert "Test Dining Table" in products
    assert "Test Chair" in products
    assert "Test Bed Frame" in products


def test_forecast_uses_historical_sales(
    client,
    db,
    optimization_cycle,
    test_products,
):
    transactions = [
        SalesTransaction(
            product_id=test_products[1].id,
            transaction_date=datetime(2026, 8, 9, 10, 0),
            quantity=Decimal("12.0000"),
            unit_price=Decimal("3500.00"),
            total_sales=Decimal("42000.00"),
            unit_profit=Decimal("949.0000"),
            total_profit=Decimal("11388.0000"),
        ),
        SalesTransaction(
            product_id=test_products[2].id,
            transaction_date=datetime(2026, 8, 9, 11, 0),
            quantity=Decimal("12.0000"),
            unit_price=Decimal("15000.00"),
            total_sales=Decimal("180000.00"),
            unit_profit=Decimal("5000.0000"),
            total_profit=Decimal("60000.0000"),
        ),
    ]

    db.add_all(transactions)
    db.commit()

    try:
        response = client.get("/api/forecast")

        assert response.status_code == 200

        data = response.json()

        products = {
            item["product_name"]: item
            for item in data["products"]
        }

        chair = products["Test Chair"]
        bed_frame = products["Test Bed Frame"]

        assert Decimal(
            chair["historical_quantity"]
        ) == Decimal("12.0000")

        assert Decimal(
            chair["forecast_quantity"]
        ) == Decimal("12.0000")

        assert chair["trend"] == "STABLE"

        assert Decimal(
            bed_frame["historical_quantity"]
        ) == Decimal("12.0000")

        assert Decimal(
            bed_frame["forecast_quantity"]
        ) == Decimal("12.0000")

        assert bed_frame["trend"] == "STABLE"

    finally:
        for transaction in transactions:
            db.delete(transaction)

        db.commit()


def test_forecast_marks_products_without_history(
    client,
    optimization_cycle,
    test_products,
):
    response = client.get("/api/forecast")

    assert response.status_code == 200

    data = response.json()

    products = {
        item["product_name"]: item
        for item in data["products"]
    }

    dining_table = products["Test Dining Table"]

    assert Decimal(
        dining_table["historical_quantity"]
    ) == Decimal("0")

    assert Decimal(
        dining_table["forecast_quantity"]
    ) == Decimal("0")

    assert dining_table["trend"] == "NO_DATA"
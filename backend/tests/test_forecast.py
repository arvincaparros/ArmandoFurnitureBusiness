from decimal import Decimal

from app.database.models import ProductionAllocation


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


def test_forecast_uses_historical_production(
    client,
    db,
    optimization_cycle,
    test_products,
):
    allocations = [
        ProductionAllocation(
            production_cycle_id=optimization_cycle.id,
            product_id=test_products[1].id,
            quantity=Decimal("12.0000"),
        ),
        ProductionAllocation(
            production_cycle_id=optimization_cycle.id,
            product_id=test_products[2].id,
            quantity=Decimal("12.0000"),
        ),
    ]

    db.add_all(allocations)
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
        for allocation in allocations:
            db.delete(allocation)

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
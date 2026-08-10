
from datetime import datetime
from decimal import Decimal

from app.database.models import (
    ForecastResult,
    ForecastRun,
    SalesTransaction,
)

from app.services.forecast_history import save_forecast_history
from app.services.forecasting import get_forecast

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

def test_generate_forecast_saves_history(
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
    ]

    db.add_all(transactions)
    db.commit()

    try:
        response = client.post(
            "/api/forecast/generate"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["forecast_period"] == "NEXT_CYCLE"

        run = (
            db.query(ForecastRun)
            .order_by(ForecastRun.id.desc())
            .first()
        )

        assert run is not None
        assert run.forecast_period == "NEXT_CYCLE"

        result = (
            db.query(ForecastResult)
            .filter(
                ForecastResult.forecast_run_id
                == run.id,
                ForecastResult.product_id
                == test_products[1].id,
            )
            .first()
        )

        assert result is not None
        assert result.historical_quantity == Decimal(
            "12.0000"
        )
        assert result.forecast_quantity == Decimal(
            "12.0000"
        )
        assert result.trend == "STABLE"

    finally:
        for transaction in transactions:
            db.delete(transaction)

        db.commit()

        latest_run = (
            db.query(ForecastRun)
            .order_by(ForecastRun.id.desc())
            .first()
        )

        if latest_run is not None:
            db.delete(latest_run)
            db.commit()

def test_get_forecast_history(
    client,
    db,
):
    forecast = get_forecast(db)
    run = save_forecast_history(db, forecast)

    try:
        response = client.get("/api/forecast/history")

        assert response.status_code == 200

        data = response.json()

        assert len(data) >= 1

        history = next(
            item
            for item in data
            if item["id"] == run.id
        )

        assert history["forecast_period"] == "NEXT_CYCLE"
        assert "created_at" in history
        assert "products" in history
        assert isinstance(history["products"], list)

    finally:
        db.delete(run)
        db.commit()

def test_get_forecast_history_latest(
    client,
    db,
):
    forecast = get_forecast(db)
    run = save_forecast_history(db, forecast)

    try:
        response = client.get(
            "/api/forecast/history/latest"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == run.id
        assert data["forecast_period"] == "NEXT_CYCLE"
        assert "created_at" in data
        assert "products" in data

    finally:
        db.delete(run)
        db.commit()

def test_get_forecast_history_run(
    client,
    db,
):
    forecast = get_forecast(db)
    run = save_forecast_history(db, forecast)

    try:
        response = client.get(
            f"/api/forecast/history/{run.id}"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == run.id
        assert data["forecast_period"] == "NEXT_CYCLE"
        assert "created_at" in data
        assert "products" in data

    finally:
        db.delete(run)
        db.commit()

def test_get_forecast_history_run_not_found(
    client,
):
    response = client.get(
        "/api/forecast/history/999999"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Forecast history run not found"
    )

def test_calculate_forecast_increasing():
    from app.services.forecasting import calculate_forecast

    historical = {
        1: [
            Decimal("10.0000"),
            Decimal("15.0000"),
            Decimal("20.0000"),
        ]
    }

    result = calculate_forecast(historical)

    assert result[1]["trend"] == "INCREASING"
    assert result[1]["forecast_quantity"] > Decimal("20.0000")


def test_calculate_forecast_decreasing():
    from app.services.forecasting import calculate_forecast

    historical = {
        1: [
            Decimal("20.0000"),
            Decimal("15.0000"),
            Decimal("10.0000"),
        ]
    }

    result = calculate_forecast(historical)

    assert result[1]["trend"] == "DECREASING"
    assert result[1]["forecast_quantity"] < Decimal("10.0000")


def test_calculate_forecast_stable():
    from app.services.forecasting import calculate_forecast

    historical = {
        1: [
            Decimal("10.0000"),
            Decimal("10.0000"),
            Decimal("10.0000"),
        ]
    }

    result = calculate_forecast(historical)

    assert result[1]["trend"] == "STABLE"
    assert result[1]["forecast_quantity"] == Decimal("10.0000")


def test_calculate_forecast_single_history():
    from app.services.forecasting import calculate_forecast

    historical = {
        1: [
            Decimal("12.0000"),
        ]
    }

    result = calculate_forecast(historical)

    assert result[1]["trend"] == "STABLE"
    assert result[1]["historical_quantity"] == Decimal("12.0000")
    assert result[1]["forecast_quantity"] == Decimal("12.0000")


def test_calculate_forecast_no_data():
    from app.services.forecasting import calculate_forecast

    result = calculate_forecast({})

    assert result == {}

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


def test_forecast_api_response_exposes_confidence_and_status(
    client,
    optimization_cycle,
    test_products,
):
    # Phase E: the live /api/forecast response now carries the
    # Phase C fields directly (previously only history did).
    response = client.get("/api/forecast")

    assert response.status_code == 200

    data = response.json()

    for product in data["products"]:
        assert "confidence_level" in product
        assert "forecast_status" in product
        assert product["confidence_level"] is not None
        assert product["forecast_status"] in (
            "NO_DATA",
            "LOW_CONFIDENCE",
            "READY",
        )


def test_forecast_api_response_uses_renamed_fields(
    client,
    optimization_cycle,
    test_products,
):
    # Phase E: historical_quantity/forecast_quantity are renamed
    # to historical_sales/predicted_demand on the live response
    # only. The old names must not appear.
    response = client.get("/api/forecast")

    assert response.status_code == 200

    data = response.json()

    for product in data["products"]:
        assert "historical_sales" in product
        assert "predicted_demand" in product
        assert "historical_quantity" not in product
        assert "forecast_quantity" not in product


def test_get_forecast_service_result_includes_confidence_and_status(
    db,
    optimization_cycle,
    test_products,
):
    forecast = get_forecast(db)

    for product in forecast["products"]:
        assert "confidence_level" in product
        assert "forecast_status" in product
        assert product["confidence_level"] is not None
        assert product["forecast_status"] in (
            "NO_DATA",
            "LOW_CONFIDENCE",
            "READY",
        )



def test_forecast_uses_historical_sales(
    client,
    db,
    optimization_cycle,
    test_products,
):
    transactions = [
        SalesTransaction(
            transaction_number="TRX-FORECAST-001",
            product_id=test_products[1].id,
            transaction_date=datetime(2026, 8, 9, 10, 0),
            quantity_produced=Decimal("12.0000"),
            quantity=Decimal("12.0000"),
            unit_price=Decimal("3500.00"),
            total_sales=Decimal("42000.00"),
            production_cost=Decimal("30612.0000"),
            unit_profit=Decimal("949.0000"),
            total_profit=Decimal("11388.0000"),
        ),
        SalesTransaction(
            transaction_number="TRX-FORECAST-002",
            product_id=test_products[2].id,
            transaction_date=datetime(2026, 8, 9, 11, 0),
            quantity_produced=Decimal("12.0000"),
            quantity=Decimal("12.0000"),
            unit_price=Decimal("15000.00"),
            total_sales=Decimal("180000.00"),
            production_cost=Decimal("120000.0000"),
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
            chair["historical_sales"]
        ) == Decimal("12.0000")

        assert Decimal(
            chair["predicted_demand"]
        ) == Decimal("12.0000")

        assert chair["trend"] == "STABLE"

        # Single month of history -> n=1 -> 8.33, LOW_CONFIDENCE
        assert Decimal(
            chair["confidence_level"]
        ) == Decimal("8.33")
        assert chair["forecast_status"] == "LOW_CONFIDENCE"

        assert Decimal(
            bed_frame["historical_sales"]
        ) == Decimal("12.0000")

        assert Decimal(
            bed_frame["predicted_demand"]
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
        dining_table["historical_sales"]
    ) == Decimal("0")

    assert Decimal(
        dining_table["predicted_demand"]
    ) == Decimal("0")

    assert dining_table["trend"] == "NO_DATA"

    # No history at all -> NO_DATA, zero confidence
    assert Decimal(
        dining_table["confidence_level"]
    ) == Decimal("0.00")
    assert dining_table["forecast_status"] == "NO_DATA"

def test_generate_forecast_saves_history(
    client,
    db,
    optimization_cycle,
    test_products,
):
    transactions = [
        SalesTransaction(
            transaction_number="TRX-FORECAST-003",
            product_id=test_products[1].id,
            transaction_date=datetime(2026, 8, 9, 10, 0),
            quantity_produced=Decimal("12.0000"),
            quantity=Decimal("12.0000"),
            unit_price=Decimal("3500.00"),
            total_sales=Decimal("42000.00"),
            production_cost=Decimal("30612.0000"),
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


def test_generate_forecast_persists_confidence_and_status(
    client,
    db,
    optimization_cycle,
    test_products,
):
    transactions = [
        SalesTransaction(
            transaction_number="TRX-FORECAST-004",
            product_id=test_products[1].id,
            transaction_date=datetime(2026, 8, 9, 10, 0),
            quantity_produced=Decimal("12.0000"),
            quantity=Decimal("12.0000"),
            unit_price=Decimal("3500.00"),
            total_sales=Decimal("42000.00"),
            production_cost=Decimal("30612.0000"),
            unit_profit=Decimal("949.0000"),
            total_profit=Decimal("11388.0000"),
        ),
    ]

    db.add_all(transactions)
    db.commit()

    try:
        response = client.post("/api/forecast/generate")

        assert response.status_code == 200

        data = response.json()

        products = {
            item["product_id"]: item
            for item in data["products"]
        }

        chair_response = products[test_products[1].id]

        assert chair_response["confidence_level"] == "8.33"
        assert chair_response["forecast_status"] == (
            "LOW_CONFIDENCE"
        )
        assert "historical_sales" in chair_response
        assert "predicted_demand" in chair_response
        assert "historical_quantity" not in chair_response
        assert "forecast_quantity" not in chair_response

        run = (
            db.query(ForecastRun)
            .order_by(ForecastRun.id.desc())
            .first()
        )

        result = (
            db.query(ForecastResult)
            .filter(
                ForecastResult.forecast_run_id == run.id,
                ForecastResult.product_id
                == test_products[1].id,
            )
            .first()
        )

        # Single-month history -> n=1 -> confidence 8.33, LOW_CONFIDENCE
        assert result.confidence_level == Decimal("8.33")
        assert result.forecast_status == "LOW_CONFIDENCE"

        # A product with no history at all still gets a persisted,
        # non-null NO_DATA status rather than being silently skipped.
        no_history_result = (
            db.query(ForecastResult)
            .filter(
                ForecastResult.forecast_run_id == run.id,
                ForecastResult.product_id
                == test_products[0].id,
            )
            .first()
        )

        assert no_history_result.confidence_level == Decimal(
            "0.00"
        )
        assert no_history_result.forecast_status == "NO_DATA"

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

def _monthly_series(*quantities):
    return [
        {
            "period": f"2026-{index + 1:02d}",
            "quantity": Decimal(str(quantity)),
        }
        for index, quantity in enumerate(quantities)
    ]


def test_calculate_forecast_no_data_zero_months():
    from app.services.forecasting import calculate_forecast

    result = calculate_forecast({1: []})

    assert result[1]["trend"] == "NO_DATA"
    assert result[1]["historical_quantity"] == Decimal("0")
    assert result[1]["forecast_quantity"] == Decimal("0")


def test_calculate_forecast_empty_input():
    from app.services.forecasting import calculate_forecast

    result = calculate_forecast({})

    assert result == {}


def test_calculate_forecast_single_month():
    from app.services.forecasting import calculate_forecast

    historical = {1: _monthly_series("12.0000")}

    result = calculate_forecast(historical)

    assert result[1]["trend"] == "STABLE"
    assert result[1]["historical_quantity"] == Decimal("12.0000")
    assert result[1]["forecast_quantity"] == Decimal("12.0000")


def test_calculate_forecast_two_months_increasing():
    from app.services.forecasting import calculate_forecast

    historical = {1: _monthly_series("10.0000", "20.0000")}

    result = calculate_forecast(historical)

    assert result[1]["trend"] == "INCREASING"
    assert result[1]["forecast_quantity"] == Decimal("30.0000")


def test_calculate_forecast_two_months_decreasing():
    from app.services.forecasting import calculate_forecast

    historical = {1: _monthly_series("20.0000", "10.0000")}

    result = calculate_forecast(historical)

    assert result[1]["trend"] == "DECREASING"
    assert result[1]["forecast_quantity"] == Decimal("0")


def test_calculate_forecast_two_months_stable():
    from app.services.forecasting import calculate_forecast

    historical = {1: _monthly_series("10.0000", "10.0000")}

    result = calculate_forecast(historical)

    assert result[1]["trend"] == "STABLE"
    assert result[1]["forecast_quantity"] == Decimal("10.0000")


def test_calculate_forecast_multiple_months_increasing():
    from app.services.forecasting import calculate_forecast

    historical = {
        1: _monthly_series("10.0000", "15.0000", "20.0000")
    }

    result = calculate_forecast(historical)

    # avg_delta = (20 - 10) / 2 = 5 -> forecast = 20 + 5 = 25
    assert result[1]["trend"] == "INCREASING"
    assert result[1]["forecast_quantity"] == Decimal("25.0000")


def test_calculate_forecast_multiple_months_decreasing():
    from app.services.forecasting import calculate_forecast

    historical = {
        1: _monthly_series("20.0000", "15.0000", "10.0000")
    }

    result = calculate_forecast(historical)

    # avg_delta = (10 - 20) / 2 = -5 -> forecast = 10 - 5 = 5
    assert result[1]["trend"] == "DECREASING"
    assert result[1]["forecast_quantity"] == Decimal("5.0000")


def test_calculate_forecast_multiple_months_stable():
    from app.services.forecasting import calculate_forecast

    historical = {
        1: _monthly_series("10.0000", "10.0000", "10.0000")
    }

    result = calculate_forecast(historical)

    assert result[1]["trend"] == "STABLE"
    assert result[1]["forecast_quantity"] == Decimal("10.0000")


def test_calculate_forecast_zero_filled_month_affects_trend():
    from app.services.forecasting import calculate_forecast

    # Jan=20, Feb=0 (zero-filled gap), Mar=20 -> flat endpoints,
    # but the zero-filled month is part of the series (n=3) and
    # the trend is still based purely on first vs. last month.
    historical = {
        1: _monthly_series("20.0000", "0", "20.0000")
    }

    result = calculate_forecast(historical)

    # avg_delta = (20 - 20) / 2 = 0 -> STABLE, forecast = 20
    assert result[1]["trend"] == "STABLE"
    assert result[1]["forecast_quantity"] == Decimal("20.0000")

    # A gap that drags the endpoint down changes the outcome:
    # Jan=20, Feb=0 (zero-filled), Mar=5.
    declining_with_gap = {
        1: _monthly_series("20.0000", "0", "5.0000")
    }

    declining_result = calculate_forecast(declining_with_gap)

    # avg_delta = (5 - 20) / 2 = -7.5 -> forecast = 5 - 7.5 = -2.5 -> clamped to 0
    assert declining_result[1]["trend"] == "DECREASING"
    assert declining_result[1]["forecast_quantity"] == Decimal("0")


def test_calculate_forecast_steep_decline_never_negative():
    from app.services.forecasting import calculate_forecast

    historical = {
        1: _monthly_series("100.0000", "50.0000", "1.0000")
    }

    result = calculate_forecast(historical)

    # avg_delta = (1 - 100) / 2 = -49.5 -> 1 - 49.5 = -48.5 -> clamped to 0
    assert result[1]["trend"] == "DECREASING"
    assert result[1]["forecast_quantity"] == Decimal("0")
    assert result[1]["forecast_quantity"] >= Decimal("0")


def _quantities(*values):
    return [Decimal(str(value)) for value in values]


def test_confidence_zero_months():
    from app.services.forecasting import calculate_forecast

    result = calculate_forecast({1: []})

    assert result[1]["confidence_level"] == Decimal("0.00")
    assert result[1]["forecast_status"] == "NO_DATA"


def test_confidence_one_month():
    from app.services.forecasting import calculate_forecast

    historical = {1: _monthly_series("12.0000")}

    result = calculate_forecast(historical)

    assert result[1]["confidence_level"] == Decimal("8.33")
    assert result[1]["forecast_status"] == "LOW_CONFIDENCE"


def test_confidence_two_months_identical_is_ready():
    from app.services.forecasting import calculate_forecast

    historical = {1: _monthly_series("20", "20")}

    result = calculate_forecast(historical)

    assert result[1]["confidence_level"] == Decimal("66.67")
    assert result[1]["forecast_status"] == "READY"


def test_confidence_two_months_volatile_is_low_confidence():
    from app.services.forecasting import calculate_forecast

    historical = {1: _monthly_series("10", "0")}

    result = calculate_forecast(historical)

    assert result[1]["confidence_level"] == Decimal("16.67")
    assert result[1]["forecast_status"] == "LOW_CONFIDENCE"


def test_confidence_mixed_four_month_series_is_ready():
    from app.services.forecasting import calculate_forecast

    historical = {1: _monthly_series("15", "0", "20", "18")}

    result = calculate_forecast(historical)

    assert result[1]["confidence_level"] == Decimal("53.70")
    assert result[1]["forecast_status"] == "READY"


def test_confidence_six_flat_months_is_max_and_ready():
    from app.services.forecasting import calculate_forecast

    historical = {
        1: _monthly_series("20", "20", "20", "20", "20", "20")
    }

    result = calculate_forecast(historical)

    assert result[1]["confidence_level"] == Decimal("100.00")
    assert result[1]["forecast_status"] == "READY"


def test_confidence_long_volatile_history_exactly_50_is_low_confidence():
    from app.services.forecasting import calculate_forecast

    historical = {
        1: _monthly_series(
            "100", "0", "100", "0", "100", "0",
            "100", "0", "100", "0", "100", "0",
        )
    }

    result = calculate_forecast(historical)

    assert result[1]["confidence_level"] == Decimal("50.00")
    assert result[1]["forecast_status"] == "LOW_CONFIDENCE"


def test_consistency_score_mean_zero_is_zero():
    from app.services.forecasting import calculate_consistency_score

    assert calculate_consistency_score(
        _quantities("0", "0", "0")
    ) == Decimal("0")


def test_confidence_level_mean_zero_series():
    from app.services.forecasting import calculate_confidence_level

    # months=3 -> data_score = 3/6*100 = 50; consistency_score = 0
    # (mean == 0) -> confidence = 0.5*50 + 0.5*0 = 25.00
    confidence = calculate_confidence_level(
        _quantities("0", "0", "0")
    )

    assert confidence == Decimal("25.00")


def test_confidence_level_is_rounded_to_two_decimal_places():
    from app.services.forecasting import calculate_confidence_level

    confidence = calculate_confidence_level(_quantities("12"))

    assert confidence == Decimal("8.33")
    assert confidence.as_tuple().exponent == -2


def test_forecast_status_boundary_exactly_50_is_low_confidence():
    from app.services.forecasting import determine_forecast_status

    assert (
        determine_forecast_status(1, Decimal("50.00"))
        == "LOW_CONFIDENCE"
    )


def test_forecast_status_just_above_50_is_ready():
    from app.services.forecasting import determine_forecast_status

    assert (
        determine_forecast_status(1, Decimal("50.01"))
        == "READY"
    )


def test_forecast_status_zero_months_is_no_data_even_with_high_confidence():
    from app.services.forecasting import determine_forecast_status

    assert (
        determine_forecast_status(0, Decimal("100.00"))
        == "NO_DATA"
    )


def test_data_score_saturates_at_six_months():
    from app.services.forecasting import calculate_data_score

    assert calculate_data_score(6) == Decimal("100")
    assert calculate_data_score(12) == Decimal("100")
    assert calculate_data_score(0) == Decimal("0")
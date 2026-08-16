from datetime import date, datetime
from decimal import Decimal

from app.database.models import SalesTransaction
from app.services.forecasting import _next_month


def _make_transaction(product_id, transaction_date, quantity):
    quantity = Decimal(str(quantity))

    return SalesTransaction(
        product_id=product_id,
        transaction_date=transaction_date,
        quantity_produced=quantity,
        quantity=quantity,
        unit_price=Decimal("10.00"),
        total_sales=quantity * Decimal("10.00"),
        production_cost=Decimal("0.00"),
        unit_profit=Decimal("0.00"),
        total_profit=Decimal("0.00"),
    )


def _add_transactions(db, transactions):
    db.add_all(transactions)
    db.commit()

    for transaction in transactions:
        db.refresh(transaction)

    return transactions


def _cleanup(db, transactions):
    for transaction in transactions:
        db.delete(transaction)

    db.commit()


def test_timeseries_multi_month_series_with_gap_and_forecast_point(
    client,
    db,
    test_products,
):
    chair = test_products[1]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(chair.id, datetime(2026, 1, 10), "10"),
            _make_transaction(chair.id, datetime(2026, 1, 25), "5"),
            _make_transaction(chair.id, datetime(2026, 3, 5), "8"),
            _make_transaction(chair.id, datetime(2026, 3, 18), "12"),
            _make_transaction(chair.id, datetime(2026, 4, 2), "18"),
        ],
    )

    try:
        response = client.get(
            "/api/forecast/timeseries",
            params={"product_id": chair.id},
        )

        assert response.status_code == 200

        data = response.json()

        assert len(data["products"]) == 1

        product_series = data["products"][0]

        assert product_series["product_id"] == chair.id
        assert product_series["product_name"] == chair.name

        series = product_series["series"]

        # 4 historical months (Jan-Apr, Feb zero-filled) + 1 forecast point
        assert len(series) == 5

        periods = [point["period"] for point in series]

        assert periods == [
            "2026-01",
            "2026-02",
            "2026-03",
            "2026-04",
            "2026-05",
        ]

        expected_historical = {
            "2026-01": "15",
            "2026-02": "0",
            "2026-03": "20",
            "2026-04": "18",
        }

        for point in series[:-1]:
            assert point["is_forecast"] is False
            assert point["predicted_demand"] is None
            assert Decimal(
                point["historical_sales"]
            ) == Decimal(
                expected_historical[point["period"]]
            )

        forecast_point = series[-1]

        assert forecast_point["period"] == "2026-05"
        assert forecast_point["is_forecast"] is True
        assert forecast_point["historical_sales"] is None

        # avg_delta = (18 - 15) / 3 = 1 -> predicted = 18 + 1 = 19
        assert Decimal(
            forecast_point["predicted_demand"]
        ) == Decimal("19")

    finally:
        _cleanup(db, transactions)


def test_timeseries_consistent_with_live_forecast_endpoint(
    client,
    db,
    test_products,
):
    chair = test_products[1]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(chair.id, datetime(2026, 1, 10), "10"),
            _make_transaction(chair.id, datetime(2026, 1, 25), "5"),
            _make_transaction(chair.id, datetime(2026, 3, 5), "8"),
            _make_transaction(chair.id, datetime(2026, 3, 18), "12"),
            _make_transaction(chair.id, datetime(2026, 4, 2), "18"),
        ],
    )

    try:
        forecast_response = client.get("/api/forecast")
        timeseries_response = client.get(
            "/api/forecast/timeseries",
            params={"product_id": chair.id},
        )

        forecast_data = {
            item["product_id"]: item
            for item in forecast_response.json()["products"]
        }[chair.id]

        timeseries_data = timeseries_response.json()["products"][0]
        forecast_point = timeseries_data["series"][-1]

        # The timeseries endpoint must reuse calculate_forecast()'s
        # output, not recompute it independently.
        assert Decimal(
            forecast_point["predicted_demand"]
        ) == Decimal(forecast_data["predicted_demand"])

    finally:
        _cleanup(db, transactions)


def test_timeseries_no_history_product_has_single_forecast_point(
    client,
    test_products,
):
    dining_table = test_products[0]

    response = client.get(
        "/api/forecast/timeseries",
        params={"product_id": dining_table.id},
    )

    assert response.status_code == 200

    data = response.json()

    series = data["products"][0]["series"]

    assert len(series) == 1

    point = series[0]

    assert point["is_forecast"] is True
    assert point["historical_sales"] is None
    assert Decimal(point["predicted_demand"]) == Decimal("0")

    today = date.today()
    expected_year, expected_month = _next_month(
        today.year,
        today.month,
    )
    expected_period = f"{expected_year:04d}-{expected_month:02d}"

    assert point["period"] == expected_period


def test_timeseries_defaults_to_all_active_products(
    client,
    test_products,
):
    response = client.get("/api/forecast/timeseries")

    assert response.status_code == 200

    data = response.json()

    product_ids = {
        item["product_id"] for item in data["products"]
    }

    assert test_products[0].id in product_ids
    assert test_products[1].id in product_ids
    assert test_products[2].id in product_ids


def test_timeseries_product_filter_returns_only_that_product(
    client,
    test_products,
):
    response = client.get(
        "/api/forecast/timeseries",
        params={"product_id": test_products[1].id},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["products"]) == 1
    assert data["products"][0]["product_id"] == test_products[1].id


def test_timeseries_unknown_product_id_returns_404(client):
    response = client.get(
        "/api/forecast/timeseries",
        params={"product_id": 999999},
    )

    assert response.status_code == 404


def test_timeseries_invalid_product_id_type_returns_422(client):
    response = client.get(
        "/api/forecast/timeseries",
        params={"product_id": "not-an-integer"},
    )

    assert response.status_code == 422


def test_timeseries_inactive_product_id_returns_404(
    client,
    db,
    test_products,
):
    product = test_products[0]
    product.is_active = False
    db.commit()

    try:
        response = client.get(
            "/api/forecast/timeseries",
            params={"product_id": product.id},
        )

        assert response.status_code == 404

    finally:
        product.is_active = True
        db.commit()


def test_timeseries_series_ordering_is_chronological_then_forecast_last(
    client,
    db,
    test_products,
):
    bed_frame = test_products[2]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(bed_frame.id, datetime(2026, 2, 1), "3"),
            _make_transaction(bed_frame.id, datetime(2026, 1, 1), "1"),
            _make_transaction(bed_frame.id, datetime(2026, 3, 1), "2"),
        ],
    )

    try:
        response = client.get(
            "/api/forecast/timeseries",
            params={"product_id": bed_frame.id},
        )

        series = response.json()["products"][0]["series"]
        periods = [point["period"] for point in series]

        assert periods == ["2026-01", "2026-02", "2026-03", "2026-04"]
        assert series[-1]["is_forecast"] is True
        assert all(
            not point["is_forecast"] for point in series[:-1]
        )

    finally:
        _cleanup(db, transactions)

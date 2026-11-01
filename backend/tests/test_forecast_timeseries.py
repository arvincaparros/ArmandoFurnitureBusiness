from datetime import date, datetime
from decimal import Decimal

from app.database.models import SalesTransaction
from app.services.forecasting import _week_start, _next_week


def _make_transaction(
    product_id,
    transaction_date,
    quantity,
    quantity_produced=None,
):
    quantity = Decimal(str(quantity))

    if quantity_produced is None:
        quantity_produced = quantity
    else:
        quantity_produced = Decimal(str(quantity_produced))

    return SalesTransaction(
        product_id=product_id,
        transaction_date=transaction_date,
        quantity_produced=quantity_produced,
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


def test_timeseries_weekly_historical_points_sum_within_week_and_zero_fill_gaps(
    client,
    db,
    test_products,
):
    """
    2026-01-05 is a Monday. Two sales inside that same week must be
    summed into one weekly point; the following week (2026-01-12)
    has no sales and must still appear, zero-filled; the week after
    that (2026-01-19) carries its own total.
    """

    chair = test_products[1]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(chair.id, datetime(2026, 1, 5), "10"),
            _make_transaction(chair.id, datetime(2026, 1, 8), "5"),
            _make_transaction(chair.id, datetime(2026, 1, 19), "20"),
        ],
    )

    try:
        response = client.get(
            "/api/forecast/timeseries",
            params={"product_id": chair.id},
        )

        assert response.status_code == 200

        data = response.json()
        product_series = data["products"][0]

        assert product_series["product_id"] == chair.id
        assert product_series["product_name"] == chair.name

        series = product_series["series"]
        historical = [
            point for point in series if not point["is_forecast"]
        ]

        periods = [point["period"] for point in historical]

        assert periods == [
            "2026-01-05",
            "2026-01-12",
            "2026-01-19",
        ]

        quantities = [
            Decimal(point["historical_sales"])
            for point in historical
        ]

        assert quantities == [
            Decimal("15"),
            Decimal("0"),
            Decimal("20"),
        ]

    finally:
        _cleanup(db, transactions)


def test_timeseries_returns_exactly_three_forecast_weeks_after_last_history(
    client,
    db,
    test_products,
):
    chair = test_products[1]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(chair.id, datetime(2026, 1, 5), "10"),
            _make_transaction(chair.id, datetime(2026, 1, 8), "5"),
            _make_transaction(chair.id, datetime(2026, 1, 19), "20"),
        ],
    )

    try:
        response = client.get(
            "/api/forecast/timeseries",
            params={"product_id": chair.id},
        )

        series = response.json()["products"][0]["series"]

        forecast_points = [
            point for point in series if point["is_forecast"]
        ]

        # Weekly quantities [15, 0, 20] -> avg_delta = (20-15)/2 =
        # 2.5 -> 22.5, 25, 27.5, each step built on the previous one.
        assert len(forecast_points) == 3
        assert [
            Decimal(point["predicted_demand"])
            for point in forecast_points
        ] == [Decimal("22.5"), Decimal("25"), Decimal("27.5")]

        # Immediately after the last historical week (2026-01-19),
        # then consecutively.
        assert [
            point["period"] for point in forecast_points
        ] == ["2026-01-26", "2026-02-02", "2026-02-09"]

        for point in forecast_points:
            assert point["historical_sales"] is None
            assert point["quantity_produced"] is None

        # Chronological throughout, forecast strictly after history.
        all_periods = [point["period"] for point in series]

        assert all_periods == sorted(all_periods)
        assert len(set(all_periods)) == len(all_periods)

    finally:
        _cleanup(db, transactions)


def test_timeseries_no_history_product_has_three_zero_forecast_points(
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
    product_series = data["products"][0]

    series = product_series["series"]

    assert len(series) == 3
    assert all(point["is_forecast"] for point in series)
    assert all(
        Decimal(point["predicted_demand"]) == Decimal("0")
        for point in series
    )
    assert all(
        point["historical_sales"] is None for point in series
    )

    assert product_series["trend"] == "NO_DATA"
    assert Decimal(product_series["confidence_level"]) == Decimal(
        "0.00"
    )

    # Week 1 starts the week after today's own week, with no
    # transaction date to anchor to.
    expected_week_1 = _next_week(_week_start(date.today()))
    expected_periods = [
        expected_week_1.strftime("%Y-%m-%d"),
        _next_week(expected_week_1).strftime("%Y-%m-%d"),
        _next_week(_next_week(expected_week_1)).strftime(
            "%Y-%m-%d"
        ),
    ]

    assert [point["period"] for point in series] == expected_periods


def test_timeseries_trend_and_confidence_are_shared_by_every_forecast_point(
    client,
    db,
    test_products,
):
    bed_frame = test_products[2]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(bed_frame.id, datetime(2026, 2, 2), "2"),
            _make_transaction(bed_frame.id, datetime(2026, 2, 16), "6"),
        ],
    )

    try:
        response = client.get(
            "/api/forecast/timeseries",
            params={"product_id": bed_frame.id},
        )

        product_series = response.json()["products"][0]

        # Weekly quantities [2, 0, 6] -> avg_delta = (6-2)/2 = 2 ->
        # increasing trend, attached once at the product level.
        assert product_series["trend"] == "INCREASING"
        assert "confidence_level" in product_series

        forecast_points = [
            point
            for point in product_series["series"]
            if point["is_forecast"]
        ]

        assert len(forecast_points) == 3

        # The field lives once on the product, not duplicated per
        # forecast point.
        for point in forecast_points:
            assert "trend" not in point
            assert "confidence_level" not in point

    finally:
        _cleanup(db, transactions)


def test_transactions_on_the_same_date_are_summed_into_one_week(
    client,
    db,
    test_products,
):
    """
    Two sales on one date must be summed into that date's weekly
    bucket, not kept as separate points - the opposite of the old
    per-transaction grain.
    """

    chair = test_products[1]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(chair.id, datetime(2026, 1, 5), "1"),
            _make_transaction(chair.id, datetime(2026, 1, 5), "4"),
        ],
    )

    try:
        response = client.get(
            "/api/forecast/timeseries",
            params={"product_id": chair.id},
        )

        series = response.json()["products"][0]["series"]
        historical = [
            point for point in series if not point["is_forecast"]
        ]

        assert len(historical) == 1
        assert historical[0]["period"] == "2026-01-05"
        assert Decimal(
            historical[0]["historical_sales"]
        ) == Decimal("5")

    finally:
        _cleanup(db, transactions)


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

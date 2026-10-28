from datetime import date, datetime
from decimal import Decimal

from app.database.models import Product, SalesTransaction
from app.services.forecasting import _next_month


# Mirrors the exported live case (transaction-history (2).csv):
# 9 qualifying transaction rows for one product ("Door (60x210)" in
# the live app). The graph must show one historical point per row
# plus exactly one forecast point, i.e. 9 rows -> 10 points.
#
# Rows are (transaction date, quantity sold, quantity produced) taken
# verbatim from the export. Sold and produced are different fields:
# the graph plots SOLD (the demand measure the forecast is built on)
# and carries produced alongside for the tooltip.
#
# Monthly sold totals reconcile to 8 / 18 / 9 (35 in total) and
# monthly produced totals to 12 / 18 / 9 (39 in total).
DOOR_TEST_PRODUCT_NAME = "Test Door (60x210)"

DOOR_TRANSACTIONS = [
    (datetime(2026, 8, 23), "1", "5"),
    (datetime(2026, 8, 27), "4", "4"),
    (datetime(2026, 8, 30), "3", "3"),
    (datetime(2026, 9, 6), "5", "5"),
    (datetime(2026, 9, 16), "5", "5"),
    (datetime(2026, 9, 20), "5", "5"),
    (datetime(2026, 9, 28), "3", "3"),
    (datetime(2026, 10, 6), "4", "4"),
    (datetime(2026, 10, 14), "5", "5"),
]

DOOR_MONTHLY_SOLD_TOTALS = {
    "2026-08": Decimal("8"),
    "2026-09": Decimal("18"),
    "2026-10": Decimal("9"),
}

DOOR_MONTHLY_PRODUCED_TOTALS = {
    "2026-08": Decimal("12"),
    "2026-09": Decimal("18"),
    "2026-10": Decimal("9"),
}


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


def test_timeseries_has_one_point_per_transaction_plus_forecast(
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

        # 5 transactions -> 5 historical points (no zero-filled
        # February any more) + 1 forecast point.
        assert len(series) == 6

        periods = [point["period"] for point in series]

        assert periods == [
            "2026-01-10",
            "2026-01-25",
            "2026-03-05",
            "2026-03-18",
            "2026-04-02",
            "2026-05-01",
        ]

        expected_historical = ["10", "5", "8", "12", "18"]

        for point, expected in zip(
            series[:-1],
            expected_historical,
        ):
            assert point["is_forecast"] is False
            assert point["predicted_demand"] is None
            assert point["transaction_id"] is not None
            assert Decimal(
                point["historical_sales"]
            ) == Decimal(expected)

        forecast_point = series[-1]

        assert forecast_point["is_forecast"] is True
        assert forecast_point["historical_sales"] is None
        assert forecast_point["transaction_id"] is None

        # The forecast still consumes MONTHLY totals - [15, 0, 20,
        # 18] with February zero-filled - not the five transaction
        # quantities: avg_delta = (18 - 15) / 3 = 1 -> 19.
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
    expected_period = f"{expected_year:04d}-{expected_month:02d}-01"

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

        assert periods == [
            "2026-01-01",
            "2026-02-01",
            "2026-03-01",
            "2026-04-01",
        ]
        assert series[-1]["is_forecast"] is True
        assert all(
            not point["is_forecast"] for point in series[:-1]
        )

    finally:
        _cleanup(db, transactions)


def _create_door_product(db):
    """
    Fresh product for the multi-transaction case. Any leftover row
    with the same test-only name (from an interrupted earlier run) is
    removed first, mirroring conftest's own scoped cleanup for its
    auth user. The name is test-prefixed so it can never collide with
    a real catalogue product.
    """

    db.query(SalesTransaction).filter(
        SalesTransaction.product_id.in_(
            db.query(Product.id).filter(
                Product.name == DOOR_TEST_PRODUCT_NAME
            )
        )
    ).delete(synchronize_session=False)

    db.query(Product).filter(
        Product.name == DOOR_TEST_PRODUCT_NAME
    ).delete(synchronize_session=False)

    db.commit()

    product = Product(
        name=DOOR_TEST_PRODUCT_NAME,
        selling_price=Decimal("4500.00"),
        labor_cost=Decimal("0.00"),
        is_active=True,
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    return product


def test_nine_transactions_produce_nine_historical_points_plus_one_forecast(
    client,
    db,
    test_products,
):
    """
    The adviser's case, rebuilt from isolated fixtures that copy the
    export row by row: 9 qualifying transaction rows for one product
    must become 9 historical points plus exactly 1 forecast point.
    """

    product = _create_door_product(db)
    other_product = test_products[0]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(product.id, day, sold, produced)
            for day, sold, produced in DOOR_TRANSACTIONS
        ]
        # A different product's sale in one of the same months, so the
        # product filter is exercised rather than assumed.
        + [
            _make_transaction(
                other_product.id,
                datetime(2026, 9, 5),
                "99",
            )
        ],
    )

    try:
        # Source of truth: the same rows the Transactions page shows.
        transactions_response = client.get("/api/transactions")

        assert transactions_response.status_code == 200

        door_rows = [
            row
            for row in transactions_response.json()
            if row["product_id"] == product.id
        ]

        assert len(door_rows) == 9

        response = client.get(
            "/api/forecast/timeseries",
            params={"product_id": product.id},
        )

        assert response.status_code == 200

        payload = response.json()

        # Product filtering: only the requested product's series.
        assert len(payload["products"]) == 1

        product_series = payload["products"][0]

        assert product_series["product_id"] == product.id
        assert product_series["product_name"] == DOOR_TEST_PRODUCT_NAME

        series = product_series["series"]

        historical = [
            point for point in series if not point["is_forecast"]
        ]
        forecast_points = [
            point for point in series if point["is_forecast"]
        ]

        # 9 transactions -> 9 historical points + 1 forecast point.
        assert len(historical) == 9
        assert len(series) == 10
        assert len(forecast_points) == 1

        # Every row keeps its own date and its own quantity sold.
        assert [
            point["period"] for point in historical
        ] == [
            day.strftime("%Y-%m-%d")
            for day, _sold, _produced in DOOR_TRANSACTIONS
        ]
        assert [
            Decimal(point["historical_sales"])
            for point in historical
        ] == [Decimal(sold) for _day, sold, _produced in DOOR_TRANSACTIONS]

        # Stable record identity: each point maps 1:1 to a real row,
        # so no row was dropped, merged or duplicated in transit.
        assert sorted(
            point["transaction_id"] for point in historical
        ) == sorted(row["id"] for row in door_rows)
        assert {
            point["transaction_number"] for point in historical
        } == {row["transaction_number"] for row in door_rows}

        for point in historical:
            assert point["predicted_demand"] is None

        # Plotted value is quantity SOLD (the demand measure the
        # forecast is built on); produced quantities travel alongside
        # and must never be mixed into the plotted series.
        assert sum(
            Decimal(point["historical_sales"])
            for point in historical
        ) == Decimal("35")
        assert sum(
            Decimal(point["quantity_produced"])
            for point in historical
        ) == Decimal("39")

        # Monthly reconciliation against the exported reference
        # totals (Aug 8 / Sep 18 / Oct 9 sold, Aug 12 / Sep 18 / Oct 9
        # produced).
        for month, expected in DOOR_MONTHLY_SOLD_TOTALS.items():
            assert sum(
                (
                    Decimal(point["historical_sales"])
                    for point in historical
                    if point["period"].startswith(month)
                ),
                Decimal("0"),
            ) == expected

        for month, expected in DOOR_MONTHLY_PRODUCED_TOTALS.items():
            assert sum(
                (
                    Decimal(point["quantity_produced"])
                    for point in historical
                    if point["period"].startswith(month)
                ),
                Decimal("0"),
            ) == expected

        # Exactly one forecast point, strictly after the last record.
        forecast_point = series[-1]

        assert forecast_point is forecast_points[0]
        assert forecast_point["period"] == "2026-11-01"
        assert forecast_point["historical_sales"] is None
        assert forecast_point["quantity_produced"] is None

        # Monthly sold totals [8, 18, 9] -> avg_delta = (9 - 8) / 2 =
        # 0.5 -> forecast = 9.5. Derived from the monthly totals, never
        # from an average of the 9 individual quantities.
        assert Decimal(
            forecast_point["predicted_demand"]
        ) == Decimal("9.5")

        # Chronological, forecast last, no shifted or duplicated dates.
        periods = [point["period"] for point in series]

        assert periods == sorted(periods)
        assert len(set(periods)) == len(periods)

    finally:
        _cleanup(db, transactions)

        db.delete(product)
        db.commit()


def test_transactions_on_the_same_date_stay_separate_points(
    client,
    db,
):
    """
    Two sales on one date must not be grouped or deduplicated: they
    stay two points with their own quantities and identities.
    """

    product = _create_door_product(db)

    same_date_transactions = [
        (datetime(2026, 8, 23), "1", "5"),
        (datetime(2026, 8, 23), "4", "4"),
    ] + DOOR_TRANSACTIONS[2:]

    assert len(same_date_transactions) == 9

    transactions = _add_transactions(
        db,
        [
            _make_transaction(product.id, day, sold, produced)
            for day, sold, produced in same_date_transactions
        ],
    )

    try:
        response = client.get(
            "/api/forecast/timeseries",
            params={"product_id": product.id},
        )

        assert response.status_code == 200

        series = response.json()["products"][0]["series"]
        historical = [
            point for point in series if not point["is_forecast"]
        ]

        # Still 9 historical points + 1 forecast: sharing a date never
        # collapses two records into one.
        assert len(historical) == 9
        assert len(series) == 10

        same_date_points = [
            point
            for point in historical
            if point["period"] == "2026-08-23"
        ]

        assert len(same_date_points) == 2

        # Each keeps its own quantity and its own transaction record.
        assert [
            Decimal(point["historical_sales"])
            for point in same_date_points
        ] == [Decimal("1"), Decimal("4")]
        assert (
            same_date_points[0]["transaction_id"]
            != same_date_points[1]["transaction_id"]
        )
        assert (
            same_date_points[0]["transaction_number"]
            != same_date_points[1]["transaction_number"]
        )

        # They occupy the first two slots, in id order, before the
        # later dates - never reordered or spread apart.
        assert historical[0] is same_date_points[0]
        assert historical[1] is same_date_points[1]

        periods = [point["period"] for point in series]

        assert periods == sorted(periods)

    finally:
        _cleanup(db, transactions)

        db.delete(product)
        db.commit()

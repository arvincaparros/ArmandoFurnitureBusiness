from datetime import date, datetime
from decimal import Decimal

from app.database.models import (
    OpeningInventoryItem,
    OpeningInventorySet,
    Product,
    SalesTransaction,
)
from app.services.forecasting import _week_start, _next_week


def _review_opening_after(db, product_id, effective_date, suffix):
    """
    A Production Cycle is no longer required to record a sale, so
    get_weekly_produced_demand's legacy fallback now also requires a
    transaction_date strictly before the ledger's REVIEWED
    effective_date to count a NULL-cycle row as genuinely pre-rollout.
    Callers pass an effective_date safely after every transaction_date
    in the test so its legacy fixtures still read as legacy.
    """

    inventory_set = OpeningInventorySet(
        set_number=f"OI-FT{suffix}",
        status="REVIEWED",
        effective_date=effective_date,
        reviewed_at=effective_date,
    )

    db.add(inventory_set)
    db.flush()

    db.add(
        OpeningInventoryItem(
            opening_inventory_set_id=inventory_set.id,
            product_id=product_id,
            quantity=Decimal("0"),
        )
    )

    db.commit()

    return inventory_set


def _cleanup_opening(db, inventory_set):
    db.query(OpeningInventoryItem).filter(
        OpeningInventoryItem.opening_inventory_set_id
        == inventory_set.id
    ).delete(synchronize_session=False)

    db.delete(inventory_set)
    db.commit()


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
    summed into one weekly SALE point; the following week
    (2026-01-12) has no sales and must still appear, zero-filled; the
    week after that (2026-01-19) carries its own total.

    This file's _make_transaction defaults quantity_produced to equal
    quantity and never sets production_cycle_id, so every transaction
    here is also a legacy row: each week that had a transaction gets
    its own PRODUCTION point too (sparse - never zero-filled, unlike
    SALE), independent of and separate from the SALE point for that
    same week.
    """

    chair = test_products[1]

    inventory_set = _review_opening_after(
        db, chair.id, datetime(2026, 2, 1), "T1",
    )

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

        sale_points = [
            point
            for point in historical
            if point["point_type"] == "SALE"
        ]
        production_points = [
            point
            for point in historical
            if point["point_type"] == "PRODUCTION"
        ]

        periods = [point["period"] for point in sale_points]

        assert periods == [
            "2026-01-05",
            "2026-01-12",
            "2026-01-19",
        ]

        quantities = [
            Decimal(point["historical_sales"])
            for point in sale_points
        ]

        assert quantities == [
            Decimal("15"),
            Decimal("0"),
            Decimal("20"),
        ]

        # The legacy fallback independently reports the same two
        # weeks' produced totals (2026-01-12 has no transaction at
        # all, so - unlike SALE - it gets no PRODUCTION point: sparse,
        # never zero-filled).
        assert [
            point["period"] for point in production_points
        ] == ["2026-01-05", "2026-01-19"]
        assert [
            Decimal(point["quantity_produced"])
            for point in production_points
        ] == [Decimal("15"), Decimal("20")]

    finally:
        _cleanup(db, transactions)
        _cleanup_opening(db, inventory_set)


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

        # Chronological throughout. Period strings are no longer
        # unique across the WHOLE series now that a week can carry
        # both a SALE and a PRODUCTION point (this file's
        # _make_transaction makes every transaction a legacy row, so
        # 2026-01-05 and 2026-01-19 each have both) - the real
        # invariant is that every forecast period comes strictly
        # after every historical one, and the forecast weeks
        # themselves are distinct and consecutive.
        all_periods = [point["period"] for point in series]

        assert all_periods == sorted(all_periods)

        historical_periods = [
            point["period"]
            for point in series
            if not point["is_forecast"]
        ]
        forecast_periods = [
            point["period"] for point in forecast_points
        ]

        assert max(historical_periods) < min(forecast_periods)
        assert len(set(forecast_periods)) == len(forecast_periods)
        assert forecast_periods == sorted(forecast_periods)

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
    Two sales on one date must be summed into that date's weekly SALE
    point, not kept as separate points - the opposite of the old
    per-transaction grain. Both rows are also legacy rows (this
    file's _make_transaction default), so the legacy fallback must
    likewise sum their quantity_produced into one weekly PRODUCTION
    point rather than two.
    """

    chair = test_products[1]

    inventory_set = _review_opening_after(
        db, chair.id, datetime(2026, 2, 1), "T2",
    )

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

        sale_points = [
            point
            for point in historical
            if point["point_type"] == "SALE"
        ]
        production_points = [
            point
            for point in historical
            if point["point_type"] == "PRODUCTION"
        ]

        assert len(sale_points) == 1
        assert sale_points[0]["period"] == "2026-01-05"
        assert Decimal(
            sale_points[0]["historical_sales"]
        ) == Decimal("5")

        assert len(production_points) == 1
        assert production_points[0]["period"] == "2026-01-05"
        assert Decimal(
            production_points[0]["quantity_produced"]
        ) == Decimal("5")

    finally:
        _cleanup(db, transactions)
        _cleanup_opening(db, inventory_set)


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


def test_timeseries_products_ordered_by_id_ascending_and_survives_unrelated_update(
    client,
    db,
):
    """
    Regression test for a dropped `.order_by(Product.id)` on
    get_forecast_timeseries()'s products_statement (present in both
    merge parents and in every sibling query in this codebase).
    Without it, Postgres is free to return active products in
    whatever order a sequential/index scan happens to encounter them
    in, and nothing stops that order from changing after any
    unrelated UPDATE to one of the rows - a classic heap-reordering
    hazard with no ORDER BY.

    Names are deliberately the REVERSE of id order (lowest id gets
    the alphabetically-last name), so this also catches an
    accidental `.order_by(Product.name)` or any other
    not-actually-id ordering - a bare set-membership check (see
    test_timeseries_defaults_to_all_active_products above) could not
    tell the difference.
    """

    products = [
        Product(
            name="Zzz Ordering Regression Product",
            selling_price=Decimal("100.00"),
            labor_cost=Decimal("0.00"),
            is_active=True,
        ),
        Product(
            name="Mmm Ordering Regression Product",
            selling_price=Decimal("100.00"),
            labor_cost=Decimal("0.00"),
            is_active=True,
        ),
        Product(
            name="Aaa Ordering Regression Product",
            selling_price=Decimal("100.00"),
            labor_cost=Decimal("0.00"),
            is_active=True,
        ),
    ]

    db.add_all(products)
    db.commit()

    for product in products:
        db.refresh(product)

    # Inserted in this order, so ids ascend in this same order - the
    # "Zzz"-named product has the lowest id, "Aaa" the highest.
    # Name-sorting would reverse this; only id-ascending is correct.
    expected_order = [product.id for product in products]

    try:
        response = client.get("/api/forecast/timeseries")
        assert response.status_code == 200

        returned_ids = [
            item["product_id"]
            for item in response.json()["products"]
            if item["product_id"] in expected_order
        ]

        assert returned_ids == expected_order

        # Force a physical row rewrite on the middle-id product -
        # the "unrelated product UPDATE" scenario the dropped
        # ORDER BY left the response order vulnerable to.
        products[1].selling_price = Decimal("200.00")
        db.commit()

        response_after_update = client.get(
            "/api/forecast/timeseries"
        )
        assert response_after_update.status_code == 200

        returned_ids_after_update = [
            item["product_id"]
            for item in response_after_update.json()["products"]
            if item["product_id"] in expected_order
        ]

        assert returned_ids_after_update == expected_order

    finally:
        for product in products:
            db.delete(product)

        db.commit()


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

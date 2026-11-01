from datetime import datetime

# Plain module name, not "tests.test_...": pytest's default (prepend)
# import mode puts backend/tests on sys.path, so this is the import
# form that does not also depend on how the runner was invoked.
from test_forecast_production_series import (
    _apply,
    _cleanup_sales,
    _make_sale,
)


def _series(client, product_id):
    response = client.get(
        "/api/forecast/timeseries",
        params={"product_id": product_id},
    )

    assert response.status_code == 200

    return response.json()["products"][0]["series"]


def test_timeseries_carries_a_production_point_per_application(
    client, db, cleanup_applications, transaction_cycle, test_products,
):
    """
    The ledger's apply event reaches the chart as its own point, with
    no sales transaction involved anywhere.
    """

    product = test_products[0]

    _apply(
        db,
        transaction_cycle.id,
        product.id,
        6,
        datetime(2026, 10, 26, 9, 0),
    )

    series = _series(client, product.id)

    production = [
        point
        for point in series
        if point["point_type"] == "PRODUCTION"
    ]

    assert len(production) == 1
    assert production[0]["period"] == "2026-10-26"
    assert production[0]["quantity_produced"] == "6.0000"
    assert production[0]["historical_sales"] is None
    assert production[0]["is_forecast"] is False
    assert production[0]["transaction_id"] is None
    assert production[0]["application_number"].startswith("PA-")


def test_production_only_product_still_gets_one_forecast_point(
    client, db, cleanup_applications, transaction_cycle, test_products,
):
    """
    With production but no sales, the series is one production point
    plus exactly one forecast point - anchored on the month AFTER the
    apply, so the forecast still sorts last.
    """

    product = test_products[0]

    _apply(
        db,
        transaction_cycle.id,
        product.id,
        6,
        datetime(2026, 10, 26, 9, 0),
    )

    series = _series(client, product.id)

    assert [point["point_type"] for point in series] == [
        "PRODUCTION",
        "FORECAST",
    ]
    assert series[-1]["period"] == "2026-11-01"
    assert series[-1]["is_forecast"] is True


def test_a_production_point_sorts_before_a_same_day_sale(
    client, db, cleanup_applications, transaction_cycle, test_products,
):
    """
    Units have to exist before they can be sold, and a fixed tie-break
    keeps the x-axis order reproducible across requests.
    """

    product = test_products[0]

    _apply(
        db,
        transaction_cycle.id,
        product.id,
        6,
        datetime(2026, 10, 27, 9, 0),
    )

    sale = _make_sale(
        db,
        product.id,
        datetime(2026, 10, 27),
        2,
        6,
        transaction_cycle.id,
        "TRX-TP0001",
    )

    try:
        series = _series(client, product.id)

        assert [point["point_type"] for point in series] == [
            "PRODUCTION",
            "SALE",
            "FORECAST",
        ]
        # The sale reports sold only: its production is the ledger's.
        assert series[1]["historical_sales"] == "2.0000"
        assert series[1]["quantity_produced"] is None

    finally:
        _cleanup_sales(db, [sale])


def test_chronological_order_interleaves_both_kinds(
    client, db, cleanup_applications, transaction_cycle, test_products,
):
    """
    Two kinds of event, one axis, strictly by date.
    """

    product = test_products[0]

    _apply(
        db,
        transaction_cycle.id,
        product.id,
        6,
        datetime(2026, 10, 26, 9, 0),
    )

    sales = [
        _make_sale(
            db,
            product.id,
            datetime(2026, 10, 28),
            2,
            0,
            transaction_cycle.id,
            "TRX-TP0002",
        ),
        _make_sale(
            db,
            product.id,
            datetime(2026, 10, 30),
            1,
            0,
            transaction_cycle.id,
            "TRX-TP0003",
        ),
    ]

    try:
        series = _series(client, product.id)

        assert [
            (point["period"], point["point_type"])
            for point in series
        ] == [
            ("2026-10-26", "PRODUCTION"),
            ("2026-10-28", "SALE"),
            ("2026-10-30", "SALE"),
            ("2026-11-01", "FORECAST"),
        ]

    finally:
        _cleanup_sales(db, sales)


def test_legacy_sale_point_keeps_its_produced_figure_and_type(
    client, db, test_products,
):
    """
    Pre-rollout behaviour, pinned at the API boundary: a legacy row is
    a SALE point that still carries the produced value the user typed.
    """

    product = test_products[0]

    sale = _make_sale(
        db,
        product.id,
        datetime(2026, 8, 23),
        1,
        5,
        None,
        "TRX-TP0004",
    )

    try:
        series = _series(client, product.id)

        assert series[0]["point_type"] == "SALE"
        assert series[0]["quantity_produced"] == "5.0000"
        assert series[0]["application_id"] is None

    finally:
        _cleanup_sales(db, [sale])

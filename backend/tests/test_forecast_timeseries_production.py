from datetime import datetime
from decimal import Decimal

from app.database.models import OpeningInventoryItem, OpeningInventorySet

# Plain module name, not "tests.test_...": pytest's default (prepend)
# import mode puts backend/tests on sys.path, so this is the import
# form that does not also depend on how the runner was invoked.
from test_forecast_production_series import (
    _apply,
    _cleanup_sales,
    _make_sale,
)


def _review_opening_after(db, product_id, effective_date, suffix):
    """
    A Production Cycle is no longer required to record a sale, so
    get_weekly_produced_demand's legacy fallback now also requires a
    transaction_date strictly before the ledger's REVIEWED
    effective_date to count a NULL-cycle row as genuinely pre-rollout.
    """

    inventory_set = OpeningInventorySet(
        set_number=f"OI-TP{suffix}",
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


def _series(client, product_id):
    response = client.get(
        "/api/forecast/timeseries",
        params={"product_id": product_id},
    )

    assert response.status_code == 200

    return response.json()["products"][0]["series"]


def test_timeseries_carries_a_production_point_per_applied_week(
    client, db, cleanup_applications, transaction_cycle, test_products,
):
    """
    The ledger's apply event reaches the chart as its own PRODUCTION
    point, bucketed by applied_at's week (2026-10-26 is a Monday),
    with no sales transaction involved anywhere. No identity field
    (transaction_id/application_id/production_cycle_id) survives on
    the combined schema - Task 1.
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
    assert "transaction_id" not in production[0]
    assert "application_id" not in production[0]
    assert "production_cycle_id" not in production[0]
    assert "application_number" not in production[0]


def test_production_only_product_still_gets_three_forecast_points(
    client, db, cleanup_applications, transaction_cycle, test_products,
):
    """
    With production but no sales, the series is one production point
    plus exactly WEEKLY_FORECAST_WEEKS (3) forecast points - anchored
    the week AFTER the applied week, so the forecast still sorts
    last.
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
        "FORECAST",
        "FORECAST",
    ]
    assert [point["period"] for point in series[1:]] == [
        "2026-11-02",
        "2026-11-09",
        "2026-11-16",
    ]
    assert all(point["is_forecast"] for point in series[1:])


def test_a_production_point_sorts_before_a_same_week_sale(
    client, db, cleanup_applications, transaction_cycle, test_products,
):
    """
    Units have to exist before they can be sold, and a fixed tie-break
    keeps the x-axis order reproducible across requests - PRODUCTION
    sorts before SALE for the same week period.
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
            "FORECAST",
            "FORECAST",
        ]
        # Both land in the same week (2026-10-26, applied Tue + sold
        # Tue), so the tie-break - not the date - decides the order.
        assert series[0]["period"] == "2026-10-26"
        assert series[1]["period"] == "2026-10-26"

        # The sale reports sold only: its production is the ledger's
        # (cycle-attributed, so the sale's own stored quantity_produced
        # is never read).
        assert series[1]["historical_sales"] == "2.0000"
        assert series[1]["quantity_produced"] is None

    finally:
        _cleanup_sales(db, [sale])


def test_chronological_order_interleaves_both_kinds(
    client, db, cleanup_applications, transaction_cycle, test_products,
):
    """
    Two independent sources, one axis, strictly by week - and sales
    inside the SAME week are summed into one SALE point, not kept as
    separate points (the weekly grain replaces the old per-transaction
    one).
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
            ("2026-10-26", "SALE"),
            ("2026-11-02", "FORECAST"),
            ("2026-11-09", "FORECAST"),
            ("2026-11-16", "FORECAST"),
        ]

        sale_point = series[1]

        assert sale_point["historical_sales"] == "3.0000"
        assert sale_point["quantity_produced"] is None

    finally:
        _cleanup_sales(db, sales)


def test_legacy_sale_produces_a_separate_sale_and_production_point(
    client, db, test_products,
):
    """
    Pre-rollout behaviour, pinned at the API boundary: a legacy row
    (production_cycle_id NULL) now surfaces as TWO points in the same
    week - a SALE point for the quantity sold, and an independent
    PRODUCTION point (from get_weekly_produced_demand's legacy
    fallback) for the stored quantity_produced. It is never one
    combined point carrying both fields.
    """

    product = test_products[0]

    inventory_set = _review_opening_after(
        db, product.id, datetime(2026, 9, 1), "L1",
    )

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

        historical = [
            point for point in series if not point["is_forecast"]
        ]

        # 2026-08-23 is a Sunday, inside the week starting 2026-08-17.
        assert len(historical) == 2

        # Same tie-break as every other week: PRODUCTION before SALE.
        assert historical[0]["point_type"] == "PRODUCTION"
        assert historical[0]["period"] == "2026-08-17"
        assert historical[0]["quantity_produced"] == "5.0000"
        assert historical[0]["historical_sales"] is None

        assert historical[1]["point_type"] == "SALE"
        assert historical[1]["period"] == "2026-08-17"
        assert historical[1]["historical_sales"] == "1.0000"
        assert historical[1]["quantity_produced"] is None

        assert "application_id" not in historical[0]
        assert "transaction_id" not in historical[1]

    finally:
        _cleanup_sales(db, [sale])
        _cleanup_opening(db, inventory_set)

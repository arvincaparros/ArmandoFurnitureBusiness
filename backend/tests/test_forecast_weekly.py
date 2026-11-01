from datetime import datetime
from decimal import Decimal

from app.database.models import SalesTransaction
from app.services.forecasting import (
    calculate_confidence_level,
    calculate_weekly_forecast,
    get_weekly_historical_demand,
)


def _make_transaction(product_id, transaction_date, quantity, quantity_produced=None):
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


# --- get_weekly_historical_demand ------------------------------------
# 2026-01-05 is a Monday, used as the anchor throughout so week
# boundaries are easy to verify by eye.


def test_multiple_transactions_same_week_are_summed(db, test_products):
    product = test_products[0]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(product.id, datetime(2026, 1, 5), "10"),
            _make_transaction(product.id, datetime(2026, 1, 8), "5"),
        ],
    )

    try:
        series = get_weekly_historical_demand(db)[product.id]

        assert series == [
            {
                "period": "2026-01-05",
                "quantity": Decimal("15"),
                "quantity_produced": Decimal("15"),
            },
        ]

    finally:
        _cleanup(db, transactions)


def test_multiple_weeks_are_separated(db, test_products):
    product = test_products[0]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(product.id, datetime(2026, 1, 5), "10"),
            _make_transaction(product.id, datetime(2026, 1, 12), "20"),
        ],
    )

    try:
        series = get_weekly_historical_demand(db)[product.id]

        assert series == [
            {
                "period": "2026-01-05",
                "quantity": Decimal("10"),
                "quantity_produced": Decimal("10"),
            },
            {
                "period": "2026-01-12",
                "quantity": Decimal("20"),
                "quantity_produced": Decimal("20"),
            },
        ]

    finally:
        _cleanup(db, transactions)


def test_missing_week_is_zero_filled(db, test_products):
    product = test_products[0]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(product.id, datetime(2026, 1, 5), "15"),
            _make_transaction(product.id, datetime(2026, 1, 19), "20"),
        ],
    )

    try:
        series = get_weekly_historical_demand(db)[product.id]

        assert series == [
            {
                "period": "2026-01-05",
                "quantity": Decimal("15"),
                "quantity_produced": Decimal("15"),
            },
            {
                "period": "2026-01-12",
                "quantity": Decimal("0"),
                "quantity_produced": Decimal("0"),
            },
            {
                "period": "2026-01-19",
                "quantity": Decimal("20"),
                "quantity_produced": Decimal("20"),
            },
        ]

    finally:
        _cleanup(db, transactions)


def test_quantity_produced_is_summed_independently_of_quantity_sold(
    db, test_products
):
    product = test_products[0]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(
                product.id, datetime(2026, 1, 5), "10", "12"
            ),
            _make_transaction(
                product.id, datetime(2026, 1, 6), "5", "5"
            ),
        ],
    )

    try:
        series = get_weekly_historical_demand(db)[product.id]

        assert series == [
            {
                "period": "2026-01-05",
                "quantity": Decimal("15"),
                "quantity_produced": Decimal("17"),
            },
        ]

    finally:
        _cleanup(db, transactions)


def test_inactive_product_excluded(db, test_products):
    product = test_products[0]
    product.is_active = False
    db.commit()

    transactions = _add_transactions(
        db,
        [_make_transaction(product.id, datetime(2026, 1, 5), "10")],
    )

    try:
        result = get_weekly_historical_demand(db)

        assert product.id not in result

    finally:
        _cleanup(db, transactions)
        product.is_active = True
        db.commit()


def test_non_positive_quantity_excluded(db, test_products):
    product = test_products[0]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(product.id, datetime(2026, 1, 5), "0"),
            _make_transaction(product.id, datetime(2026, 1, 12), "5"),
        ],
    )

    try:
        series = get_weekly_historical_demand(db)[product.id]

        assert series == [
            {
                "period": "2026-01-12",
                "quantity": Decimal("5"),
                "quantity_produced": Decimal("5"),
            },
        ]

    finally:
        _cleanup(db, transactions)


def test_chronological_ordering(db, test_products):
    product = test_products[0]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(product.id, datetime(2026, 1, 19), "3"),
            _make_transaction(product.id, datetime(2026, 1, 5), "1"),
            _make_transaction(product.id, datetime(2026, 1, 12), "2"),
        ],
    )

    try:
        series = get_weekly_historical_demand(db)[product.id]

        periods = [item["period"] for item in series]

        assert periods == [
            "2026-01-05",
            "2026-01-12",
            "2026-01-19",
        ]

    finally:
        _cleanup(db, transactions)


def test_product_isolation(db, test_products):
    product_a = test_products[0]
    product_b = test_products[1]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(product_a.id, datetime(2026, 1, 5), "10"),
            _make_transaction(product_b.id, datetime(2026, 1, 5), "99"),
            _make_transaction(product_b.id, datetime(2026, 1, 12), "1"),
        ],
    )

    try:
        result = get_weekly_historical_demand(db)

        assert result[product_a.id] == [
            {
                "period": "2026-01-05",
                "quantity": Decimal("10"),
                "quantity_produced": Decimal("10"),
            },
        ]

        assert result[product_b.id] == [
            {
                "period": "2026-01-05",
                "quantity": Decimal("99"),
                "quantity_produced": Decimal("99"),
            },
            {
                "period": "2026-01-12",
                "quantity": Decimal("1"),
                "quantity_produced": Decimal("1"),
            },
        ]

    finally:
        _cleanup(db, transactions)


# --- calculate_weekly_forecast ----------------------------------------


def test_zero_weeks_forecast_is_flat_zero_with_no_data_trend():
    forecasts = calculate_weekly_forecast({1: []})

    assert forecasts[1]["forecast_quantities"] == [
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
    ]
    assert forecasts[1]["trend"] == "NO_DATA"
    assert forecasts[1]["confidence_level"] == Decimal("0.00")


def test_single_week_forecast_flat_carries_with_stable_trend():
    weekly = {1: [{"period": "2026-01-05", "quantity": Decimal("8")}]}

    forecasts = calculate_weekly_forecast(weekly)

    assert forecasts[1]["forecast_quantities"] == [
        Decimal("8"),
        Decimal("8"),
        Decimal("8"),
    ]
    assert forecasts[1]["trend"] == "STABLE"


def test_multi_week_forecast_extrapolates_three_points():
    weekly = {
        1: [
            {"period": "2026-01-05", "quantity": Decimal("10")},
            {"period": "2026-01-12", "quantity": Decimal("20")},
            {"period": "2026-01-19", "quantity": Decimal("30")},
        ],
    }

    forecasts = calculate_weekly_forecast(weekly)

    # avg_delta = (30 - 10) / 2 = 10, applied on top of each
    # successive forecast point.
    assert forecasts[1]["forecast_quantities"] == [
        Decimal("40"),
        Decimal("50"),
        Decimal("60"),
    ]
    assert forecasts[1]["trend"] == "INCREASING"


def test_decreasing_trend_forecast_clamps_at_zero():
    weekly = {
        1: [
            {"period": "2026-01-05", "quantity": Decimal("10")},
            {"period": "2026-01-12", "quantity": Decimal("2")},
        ],
    }

    forecasts = calculate_weekly_forecast(weekly)

    # avg_delta = (2 - 10) / 1 = -8: 2-8 clamps to 0, and stays 0.
    assert forecasts[1]["forecast_quantities"] == [
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
    ]
    assert forecasts[1]["trend"] == "DECREASING"


def test_confidence_level_reuses_the_shared_formula():
    quantities = [Decimal("10"), Decimal("20"), Decimal("30")]
    weekly = {
        1: [
            {"period": "2026-01-05", "quantity": quantities[0]},
            {"period": "2026-01-12", "quantity": quantities[1]},
            {"period": "2026-01-19", "quantity": quantities[2]},
        ],
    }

    forecasts = calculate_weekly_forecast(weekly)

    assert forecasts[1]["confidence_level"] == calculate_confidence_level(
        quantities
    )


def test_num_weeks_is_configurable():
    weekly = {1: [{"period": "2026-01-05", "quantity": Decimal("5")}]}

    forecasts = calculate_weekly_forecast(weekly, num_weeks=5)

    assert forecasts[1]["forecast_quantities"] == [Decimal("5")] * 5

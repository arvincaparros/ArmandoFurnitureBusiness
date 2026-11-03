from datetime import datetime
from decimal import Decimal

from app.database.models import ProductionApplication, SalesTransaction
from app.services.forecasting import (
    _week_start,
    calculate_confidence_level,
    calculate_weekly_forecast,
    get_weekly_historical_demand,
    get_weekly_produced_demand,
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
            },
            {
                "period": "2026-01-12",
                "quantity": Decimal("20"),
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
            },
            {
                "period": "2026-01-12",
                "quantity": Decimal("0"),
            },
            {
                "period": "2026-01-19",
                "quantity": Decimal("20"),
            },
        ]

    finally:
        _cleanup(db, transactions)


def test_weekly_produced_sums_legacy_pre_rollout_rows_independently_of_sold(
    db, test_products,
):
    """
    get_weekly_historical_demand (SOLD) and get_weekly_produced_demand
    (PRODUCED) are two independent data sources now, not one combined
    figure - this proves PRODUCED sums its own column independently of
    whatever was SOLD that week. No ledger application exists in this
    test, so both rows must have production_cycle_id=None (the model
    default _make_transaction leaves untouched) for their
    quantity_produced to count at all under the new sourcing rule.
    """

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
        sold = get_weekly_historical_demand(db)[product.id]
        produced = get_weekly_produced_demand(db)[product.id]

        assert sold == [
            {"period": "2026-01-05", "quantity": Decimal("15")},
        ]
        assert produced == [
            {
                "period": "2026-01-05",
                "quantity_produced": Decimal("17"),
            },
        ]

    finally:
        _cleanup(db, transactions)


def test_weekly_produced_sums_ledger_applications_by_applied_week(
    db, test_products, two_cycles,
):
    """
    get_weekly_produced_demand's ledger half buckets by its own
    ProductionApplication.applied_at week, not by the cycle's
    start_date. applied_at is deliberately forced here (rather than
    left as whatever apply_production_to_cycle's save_production_
    application stamps - the real current time at test-run) so this
    assertion is anchored to a fixed, known week and never flaps
    depending on what day the suite happens to run.

    applied_at (2026-10-20, week-of 2026-10-19) is deliberately chosen
    to fall in a DIFFERENT calendar week than two_cycles' first cycle,
    whose start_date (2026-10-30) is week-of 2026-10-26 and whose
    end_date (2026-11-06) is week-of 2026-11-02. If get_weekly_
    produced_demand ever regressed to bucketing by the cycle's own
    dates instead of applied_at, this test would then assert the wrong
    period and fail.
    """

    from app.database.models import OptimizationRun
    from app.services.production_application import (
        save_production_application,
    )

    first, _second = two_cycles
    product = test_products[0]

    applied_at = datetime(2026, 10, 20, 9, 0)

    def _apply(quantity):
        run = OptimizationRun(
            production_cycle_id=first.id,
            started_at=applied_at,
            status="OPTIMAL",
        )

        db.add(run)
        db.commit()
        db.refresh(run)

        application = save_production_application(
            db,
            first.id,
            run.id,
            {product.id: Decimal(str(quantity))},
            [],
        )
        application.applied_at = applied_at

        db.commit()
        db.refresh(application)

        return application

    _apply(6)
    _apply(4)

    produced = get_weekly_produced_demand(db)[product.id]

    week_of_applications = _week_start(applied_at).strftime(
        "%Y-%m-%d"
    )

    assert produced == [
        {
            "period": week_of_applications,
            "quantity_produced": Decimal("10"),
        },
    ]


def test_weekly_produced_legacy_fallback_excludes_cycle_attributed_rows(
    db, test_products, transaction_cycle,
):
    """
    The legacy fallback counts a SalesTransaction's own
    quantity_produced ONLY when production_cycle_id IS NULL. A row in
    the SAME week WITH production_cycle_id set must contribute
    nothing, even though it also carries a nonzero quantity_produced -
    otherwise a post-rollout sale would double up with its own
    ledger-recorded production.
    """

    product = test_products[0]

    legacy_sale = _make_transaction(
        product.id,
        datetime(2026, 10, 26),
        quantity=2,
        quantity_produced=9,
    )

    transactions = _add_transactions(db, [legacy_sale])

    cycle_attributed_sale = SalesTransaction(
        transaction_number="TRX-LEGFB0001",
        product_id=product.id,
        production_cycle_id=transaction_cycle.id,
        transaction_date=datetime(2026, 10, 26),
        quantity=Decimal("2"),
        quantity_produced=Decimal("9"),
        unit_price=Decimal("10.00"),
        total_sales=Decimal("20.00"),
        production_cost=Decimal("0.00"),
        unit_profit=Decimal("0.00"),
        total_profit=Decimal("0.00"),
    )

    db.add(cycle_attributed_sale)
    db.commit()
    db.refresh(cycle_attributed_sale)

    try:
        produced = get_weekly_produced_demand(db).get(product.id, [])

        # Only the legacy row's 9 counts. If the cycle-attributed
        # row's quantity_produced leaked in too, this would be 18.
        assert produced == [
            {
                "period": "2026-10-26",
                "quantity_produced": Decimal("9"),
            },
        ]

    finally:
        db.delete(cycle_attributed_sale)
        db.commit()
        _cleanup(db, transactions)


def test_weekly_produced_never_double_counts_a_cycle_attributed_sales_own_stored_quantity_produced(
    db, test_products, transaction_cycle,
):
    """
    THE regression test for the bug this whole integration exists to
    fix. Apply real production (6 units) into a cycle through the
    ledger, then directly construct - via the ORM, exactly like a
    stale pre-ledger write would look - a SalesTransaction for that
    SAME week with production_cycle_id SET to that cycle (i.e. NOT a
    legacy row) and an explicit, large, MISMATCHED stored
    quantity_produced (999, not 6). get_weekly_produced_demand must
    report exactly 6 for that week - never 6 + 999, and never 999 -
    proving the sale's own stale quantity_produced can never leak into
    the production figure once a ledger entry exists for the cycle.
    """

    from conftest import apply_production_to_cycle

    product = test_products[0]

    apply_production_to_cycle(db, transaction_cycle.id, product.id, 6)

    application = (
        db.query(ProductionApplication)
        .filter(
            ProductionApplication.production_cycle_id
            == transaction_cycle.id
        )
        .one()
    )

    sale = SalesTransaction(
        transaction_number="TRX-DBLCT0001",
        product_id=product.id,
        production_cycle_id=transaction_cycle.id,
        transaction_date=application.applied_at,
        quantity=Decimal("1"),
        quantity_produced=Decimal("999"),
        unit_price=Decimal("10.00"),
        total_sales=Decimal("10.00"),
        production_cost=Decimal("0.00"),
        unit_profit=Decimal("0.00"),
        total_profit=Decimal("0.00"),
    )

    db.add(sale)
    db.commit()
    db.refresh(sale)

    try:
        produced = get_weekly_produced_demand(db)[product.id]

        week = _week_start(application.applied_at).strftime(
            "%Y-%m-%d"
        )

        assert produced == [
            {
                "period": week,
                "quantity_produced": Decimal("6"),
            },
        ]

    finally:
        db.delete(sale)
        db.commit()


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
            },
        ]

        assert result[product_b.id] == [
            {
                "period": "2026-01-05",
                "quantity": Decimal("99"),
            },
            {
                "period": "2026-01-12",
                "quantity": Decimal("1"),
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

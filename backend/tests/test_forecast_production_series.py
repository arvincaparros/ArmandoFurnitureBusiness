from datetime import datetime
from decimal import Decimal

from app.database.models import (
    OpeningInventoryItem,
    OpeningInventorySet,
    OptimizationRun,
    SalesTransaction,
)

# Plain module name - pytest's prepend import mode puts
# backend/tests on sys.path.
from conftest import purge_ledger


def _make_run(db, cycle_id, started_at):
    run = OptimizationRun(
        production_cycle_id=cycle_id,
        started_at=started_at,
        status="OPTIMAL",
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    return run


def _apply(db, cycle_id, product_id, quantity, applied_at):
    """
    Write one ledger application, then force its applied_at:
    save_production_application stamps "now", and these tests need
    deterministic event dates on the chart's x-axis.
    """

    from app.services.production_application import (
        save_production_application,
    )

    run = _make_run(db, cycle_id, applied_at)

    application = save_production_application(
        db,
        cycle_id,
        run.id,
        {product_id: Decimal(str(quantity))},
        [],
    )

    application.applied_at = applied_at

    db.commit()
    db.refresh(application)

    return application


def _make_sale(
    db,
    product_id,
    transaction_date,
    quantity,
    quantity_produced,
    production_cycle_id,
    number,
):
    sale = SalesTransaction(
        transaction_number=number,
        product_id=product_id,
        production_cycle_id=production_cycle_id,
        transaction_date=transaction_date,
        quantity=Decimal(str(quantity)),
        quantity_produced=Decimal(str(quantity_produced)),
        unit_price=Decimal("100.00"),
        total_sales=Decimal(str(quantity)) * Decimal("100.00"),
        production_cost=Decimal("0.00"),
        unit_profit=Decimal("0.00"),
        total_profit=Decimal("0.00"),
    )

    db.add(sale)
    db.commit()
    db.refresh(sale)

    return sale


def _cleanup_sales(db, sales):
    for sale in sales:
        db.delete(sale)

    db.commit()


def test_production_event_series_has_one_point_per_application(
    db, cleanup_applications, transaction_cycle, test_products,
):
    """
    The series is sourced from the ledger, so one apply is one point -
    dated when it was applied, carrying its application number.
    """

    from app.services.forecasting import (
        get_production_event_series,
    )

    product = test_products[0]

    _apply(
        db,
        transaction_cycle.id,
        product.id,
        6,
        datetime(2026, 10, 26, 9, 0),
    )

    events = get_production_event_series(db)[product.id]

    assert len(events) == 1
    assert events[0]["period"] == "2026-10-26"
    assert events[0]["quantity_produced"] == Decimal("6")
    assert events[0]["production_cycle_id"] == transaction_cycle.id
    assert events[0]["application_number"].startswith("PA-")


def test_production_appears_with_no_sales_transaction_at_all(
    db, cleanup_applications, transaction_cycle, test_products,
):
    """
    The requirement the drawdown approach could not meet: production
    is visible on the chart before anything has been sold.
    """

    from app.services.forecasting import (
        get_production_event_series,
    )

    product = test_products[0]

    _apply(
        db,
        transaction_cycle.id,
        product.id,
        12,
        datetime(2026, 10, 26, 9, 0),
    )

    events = get_production_event_series(db)[product.id]

    assert [event["quantity_produced"] for event in events] == [
        Decimal("12"),
    ]


def test_many_sales_do_not_duplicate_one_application(
    db, cleanup_applications, transaction_cycle, test_products,
):
    """
    Production is no longer carried by sales rows, so five sales drawn
    from one applied batch still report exactly 10 produced units.
    """

    from app.services.forecasting import (
        get_production_event_series,
    )

    product = test_products[0]

    _apply(
        db,
        transaction_cycle.id,
        product.id,
        10,
        datetime(2026, 10, 26, 9, 0),
    )

    sales = [
        _make_sale(
            db,
            product.id,
            datetime(2026, 10, 27 + index),
            1,
            0,
            transaction_cycle.id,
            f"TRX-PS{index:04d}",
        )
        for index in range(5)
    ]

    try:
        events = get_production_event_series(db)[product.id]

        assert sum(
            event["quantity_produced"] for event in events
        ) == Decimal("10")

    finally:
        _cleanup_sales(db, sales)


def test_opening_inventory_is_never_reported_as_produced(
    db, cleanup_applications, cleanup_opening_inventory,
    transaction_cycle, test_products,
):
    """
    Opening inventory is a starting balance, not production. The
    series joins production_application_items only - it must not know
    opening_inventory_items exists.
    """

    from app.services.forecasting import (
        get_production_event_series,
    )

    product = test_products[0]

    inventory_set = OpeningInventorySet(
        set_number="OI-PS01",
        status="REVIEWED",
        effective_date=datetime(2026, 10, 1),
        reviewed_at=datetime(2026, 10, 1),
    )

    db.add(inventory_set)
    db.flush()

    db.add(
        OpeningInventoryItem(
            opening_inventory_set_id=inventory_set.id,
            product_id=product.id,
            quantity=Decimal("40"),
        )
    )

    db.commit()

    _apply(
        db,
        transaction_cycle.id,
        product.id,
        6,
        datetime(2026, 10, 26, 9, 0),
    )

    events = get_production_event_series(db)[product.id]

    assert sum(
        event["quantity_produced"] for event in events
    ) == Decimal("6")


def test_previous_cycle_production_stays_on_its_own_date(
    db, cleanup_applications, test_products,
):
    """
    Last cycle's production is history: it keeps its own point and its
    own cycle id, and is never re-counted into the new cycle's point.
    """

    from app.database.models import ProductionCycle
    from app.services.forecasting import (
        get_production_event_series,
    )

    product = test_products[0]

    first = ProductionCycle(
        cycle_date=datetime(2026, 10, 11),
        start_date=datetime(2026, 10, 11),
        end_date=datetime(2026, 10, 18),
        # COMPLETED, not "CLOSED": CLOSED is not one of
        # ProductionCycleStatus's values, so a leftover row carrying it
        # makes GET /api/production-cycles fail response validation for
        # an unrelated test. The status is incidental to what this test
        # asserts (that a previous cycle's production keeps its own
        # date); it just needs to be a finished cycle.
        status="COMPLETED",
    )

    second = ProductionCycle(
        cycle_date=datetime(2026, 10, 18),
        start_date=datetime(2026, 10, 18),
        end_date=datetime(2026, 10, 25),
        status="OPEN",
    )

    db.add_all([first, second])
    db.commit()
    db.refresh(first)
    db.refresh(second)

    try:
        _apply(
            db,
            first.id,
            product.id,
            8,
            datetime(2026, 10, 12, 9, 0),
        )
        _apply(
            db,
            second.id,
            product.id,
            5,
            datetime(2026, 10, 19, 9, 0),
        )

        events = get_production_event_series(db)[product.id]

        assert [
            (
                event["period"],
                event["production_cycle_id"],
                event["quantity_produced"],
            )
            for event in events
        ] == [
            ("2026-10-12", first.id, Decimal("8")),
            ("2026-10-19", second.id, Decimal("5")),
        ]

    finally:
        # Scoped ledger purge first: production_applications RESTRICTs
        # optimization_run_id, so the ORM cascade from
        # ProductionCycle.optimization_runs on the deletes below is
        # refused while an application still points at a run. Scoped to
        # these two cycles only.
        purge_ledger(db, cycle_ids=[first.id, second.id])

        db.delete(second)
        db.delete(first)
        db.commit()


def test_inactive_products_are_excluded(
    db, cleanup_applications, transaction_cycle, test_products,
):
    """
    Same qualification rule as the sales layer, so a product can never
    appear in one series and be missing from the other.
    """

    from app.services.forecasting import (
        get_production_event_series,
    )

    product = test_products[0]

    _apply(
        db,
        transaction_cycle.id,
        product.id,
        6,
        datetime(2026, 10, 26, 9, 0),
    )

    product.is_active = False
    db.commit()

    try:
        assert product.id not in get_production_event_series(db)

    finally:
        product.is_active = True
        db.commit()


def test_legacy_sale_keeps_reporting_its_stored_produced_quantity(
    db, test_products,
):
    """
    Pre-rollout rows have production_cycle_id NULL and no ledger entry
    anywhere. Their stored quantity_produced is the only production
    record they will ever have, so the sales layer must keep handing
    it to the chart byte-for-byte.
    """

    from app.services.forecasting import (
        get_transaction_historical_demand,
    )

    product = test_products[0]

    sale = _make_sale(
        db,
        product.id,
        datetime(2026, 8, 23),
        1,
        5,
        None,
        "TRX-PS9001",
    )

    try:
        history = get_transaction_historical_demand(db)[product.id]

        assert history[0]["quantity_produced"] == Decimal("5")

    finally:
        _cleanup_sales(db, [sale])


def test_cycle_attributed_sale_reports_no_produced_quantity(
    db, transaction_cycle, test_products,
):
    """
    A post-rollout row's production lives in the ledger. Reporting its
    stored quantity_produced here too would plot the same units twice.
    """

    from app.services.forecasting import (
        get_transaction_historical_demand,
    )

    product = test_products[0]

    sale = _make_sale(
        db,
        product.id,
        datetime(2026, 10, 27),
        1,
        6,
        transaction_cycle.id,
        "TRX-PS9002",
    )

    try:
        history = get_transaction_historical_demand(db)[product.id]

        assert history[0]["quantity"] == Decimal("1")
        assert history[0]["quantity_produced"] is None

    finally:
        _cleanup_sales(db, [sale])

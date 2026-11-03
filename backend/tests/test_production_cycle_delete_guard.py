from datetime import datetime
from decimal import Decimal

import pytest

from sqlalchemy.exc import IntegrityError

from app.database.models import (
    OpeningInventoryItem,
    OpeningInventorySet,
    OptimizationRun,
    ProductionApplication,
    ProductionApplicationItem,
    ProductionCycle,
)


def _make_cycle(db, cycle_date):
    cycle = ProductionCycle(
        cycle_date=cycle_date,
        start_date=cycle_date,
        end_date=cycle_date,
        status="OPEN",
    )

    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    return cycle


def _make_run(db, cycle_id, started_at):
    run = OptimizationRun(
        production_cycle_id=cycle_id,
        started_at=started_at,
        completed_at=started_at,
        status="OPTIMAL",
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    return run


def _make_application(
    db, cycle_id, run_id, application_number, product_id, quantity,
):
    application = ProductionApplication(
        application_number=application_number,
        production_cycle_id=cycle_id,
        optimization_run_id=run_id,
        applied_at=datetime(2026, 10, 30, 9, 0),
    )

    db.add(application)
    db.flush()

    db.add(
        ProductionApplicationItem(
            production_application_id=application.id,
            product_id=product_id,
            quantity_produced=quantity,
        )
    )

    db.commit()
    db.refresh(application)

    return application


def _purge_ledger(db, application_id=None, run_id=None, cycle=None):
    """
    Explicit teardown run from inside each test, before the test
    function returns - not left to fixture teardown ordering. Several
    of these tests share `test_products` with its own fixture, which
    tears down with a bare `db.delete(product)`; now that
    ProductionApplicationItem.product_id is RESTRICT, that delete
    would raise IntegrityError if a ledger row created here still
    pointed at the product, and fixture teardown order relative to a
    same-scope sibling fixture is not something to rely on.
    """

    if application_id is not None:
        db.query(ProductionApplicationItem).filter(
            ProductionApplicationItem.production_application_id
            == application_id
        ).delete(synchronize_session=False)

        db.query(ProductionApplication).filter(
            ProductionApplication.id == application_id
        ).delete(synchronize_session=False)

    if run_id is not None:
        db.query(OptimizationRun).filter(
            OptimizationRun.id == run_id
        ).delete(synchronize_session=False)

    db.commit()

    if cycle is not None:
        db.delete(cycle)
        db.commit()


def test_delete_blocked_when_cycle_has_production_application(
    client, db, test_products,
):
    """
    The point of the whole correction: deleting a cycle that
    production has been applied to must be refused with a 409 that
    names the blocking application, and the ledger row (and its
    items) must still be there afterwards - not merely report a
    status code that happens to be right while the data underneath
    was already destroyed.
    """

    cycle = _make_cycle(db, datetime(2026, 10, 30))
    run = _make_run(db, cycle.id, datetime(2026, 10, 30, 9, 0))
    application = _make_application(
        db,
        cycle.id,
        run.id,
        "PA-GUARD1",
        test_products[0].id,
        Decimal("10.0000"),
    )

    application_id = application.id
    run_id = run.id

    try:
        response = client.delete(
            f"/api/production-cycles/{cycle.id}"
        )

        assert response.status_code == 409
        assert "PA-GUARD1" in response.json()["detail"]

        db.expire_all()

        surviving_application = db.get(
            ProductionApplication, application_id
        )
        assert surviving_application is not None
        assert surviving_application.production_cycle_id == cycle.id

        surviving_items = (
            db.query(ProductionApplicationItem)
            .filter(
                ProductionApplicationItem.production_application_id
                == application_id
            )
            .all()
        )
        assert len(surviving_items) == 1
        assert surviving_items[0].quantity_produced == (
            Decimal("10.0000")
        )

        surviving_cycle = db.get(ProductionCycle, cycle.id)
        assert surviving_cycle is not None

    finally:
        _purge_ledger(db, application_id, run_id, cycle)


def test_delete_succeeds_when_cycle_has_no_applications(client, db):
    """
    Regression guard: a cycle with no production history must still
    delete exactly as before the correction.
    """

    cycle = _make_cycle(db, datetime(2026, 10, 31))
    cycle_id = cycle.id

    response = client.delete(
        f"/api/production-cycles/{cycle_id}"
    )

    assert response.status_code == 204

    db.expire_all()
    assert db.get(ProductionCycle, cycle_id) is None


def test_raw_cycle_delete_with_application_raises_integrity_error(
    db, test_products,
):
    """
    Database-level proof that RESTRICT is real, not just an
    application-layer check: bypassing the service guard entirely
    with a bare db.delete/db.commit must still fail.
    """

    cycle = _make_cycle(db, datetime(2026, 11, 1))
    run = _make_run(db, cycle.id, datetime(2026, 11, 1, 9, 0))
    application = _make_application(
        db,
        cycle.id,
        run.id,
        "PA-GUARD2",
        test_products[0].id,
        Decimal("5.0000"),
    )

    application_id = application.id
    run_id = run.id

    db.delete(cycle)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()

    _purge_ledger(db, application_id, run_id, cycle)


def test_raw_product_delete_blocked_by_reviewed_opening_inventory(
    db, test_products,
):
    """
    Protects reviewed opening inventory records: a product still
    referenced by a REVIEWED set's items must not be deletable, since
    that would silently corrupt the one authoritative opening balance
    every derived stock figure depends on.
    """

    product = test_products[0]

    inventory_set = OpeningInventorySet(
        set_number="OI-GUARD1",
        status="REVIEWED",
        effective_date=datetime(2026, 10, 30),
        reviewed_at=datetime(2026, 10, 30),
    )

    db.add(inventory_set)
    db.flush()

    item = OpeningInventoryItem(
        opening_inventory_set_id=inventory_set.id,
        product_id=product.id,
        quantity=Decimal("3.0000"),
    )

    db.add(item)
    db.commit()

    inventory_set_id = inventory_set.id
    item_id = item.id

    db.delete(product)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()

    db.query(OpeningInventoryItem).filter(
        OpeningInventoryItem.id == item_id
    ).delete(synchronize_session=False)

    db.query(OpeningInventorySet).filter(
        OpeningInventorySet.id == inventory_set_id
    ).delete(synchronize_session=False)

    db.commit()


def test_raw_product_delete_blocked_by_production_application_item(
    db, test_products,
):
    """
    Same guarantee for the production-application side of the
    ledger: a product that an apply event produced units of must not
    be deletable either.
    """

    product = test_products[1]

    cycle = _make_cycle(db, datetime(2026, 11, 2))
    run = _make_run(db, cycle.id, datetime(2026, 11, 2, 9, 0))
    application = _make_application(
        db,
        cycle.id,
        run.id,
        "PA-GUARD3",
        product.id,
        Decimal("2.0000"),
    )

    application_id = application.id
    run_id = run.id

    db.delete(product)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()

    _purge_ledger(db, application_id, run_id, cycle)

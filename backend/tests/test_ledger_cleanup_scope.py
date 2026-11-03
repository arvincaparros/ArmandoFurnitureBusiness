"""
The regression guard for scoped ledger cleanup (Task 24).

A SENTINEL ledger row - one owned by no fixture - must survive every
fixture purge in the suite. Until Task 6 this was a theoretical
concern: no service wrote the ledger, so wiping both tables wholesale
was harmless. apply_optimization now appends a real application on
every apply, so a blanket purge from a shared fixture would destroy
rows another test legitimately created. These tests are what make the
scoping real instead of aspirational.

The sentinel deliberately owns its OWN product, cycle and run, so it
sits outside every id a fixture could pass to purge_ledger. It is
module-scoped and carries its own Session: the `db` fixture is
function-scoped and cannot be depended on from module scope.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from app.database.connection import SessionLocal
from app.database.models import (
    OpeningInventoryItem,
    OpeningInventorySet,
    OptimizationRun,
    Product,
    ProductionApplication,
    ProductionApplicationItem,
    ProductionCycle,
)

from conftest import purge_ledger


SENTINEL_APPLICATION_NUMBER = "PA-SENTINEL"
SENTINEL_SET_NUMBER = "OI-SENTINEL"


@pytest.fixture(scope="module")
def sentinel_ledger():
    """
    One application + one opening-inventory set that no fixture owns,
    created once for the module and asserted to still exist after the
    row-owning fixtures have set up and torn down around it.
    """

    session = SessionLocal()

    product = Product(
        name="Sentinel Ledger Product",
        selling_price=Decimal("999.00"),
        labor_cost=Decimal("0.00"),
        is_active=True,
    )

    cycle = ProductionCycle(
        cycle_date=datetime(2027, 1, 4),
        start_date=datetime(2027, 1, 4),
        end_date=datetime(2027, 1, 11),
        status="OPEN",
    )

    session.add_all([product, cycle])
    session.commit()
    session.refresh(product)
    session.refresh(cycle)

    run = OptimizationRun(
        production_cycle_id=cycle.id,
        started_at=datetime(2027, 1, 4, 9, 0),
        completed_at=datetime(2027, 1, 4, 9, 0, 1),
        status="OPTIMAL",
    )

    session.add(run)
    session.commit()
    session.refresh(run)

    application = ProductionApplication(
        application_number=SENTINEL_APPLICATION_NUMBER,
        production_cycle_id=cycle.id,
        optimization_run_id=run.id,
        applied_at=datetime(2027, 1, 4, 9, 0, 2),
    )

    session.add(application)
    session.flush()

    session.add(
        ProductionApplicationItem(
            production_application_id=application.id,
            product_id=product.id,
            quantity_produced=Decimal("7.0000"),
        )
    )

    inventory_set = OpeningInventorySet(
        set_number=SENTINEL_SET_NUMBER,
        status="DRAFT",
        effective_date=datetime(2027, 1, 4),
        notes="sentinel - must survive every fixture purge",
    )

    session.add(inventory_set)
    session.flush()

    session.add(
        OpeningInventoryItem(
            opening_inventory_set_id=inventory_set.id,
            product_id=product.id,
            quantity=Decimal("3.0000"),
        )
    )

    session.commit()

    ids = {
        "product_id": product.id,
        "cycle_id": cycle.id,
        "run_id": run.id,
        "application_id": application.id,
        "set_id": inventory_set.id,
    }

    yield ids

    # Teardown in the same five-table FK order, then the rows the
    # sentinel owns. all_rows is NOT used: this fixture must not
    # become the thing that wipes the table it exists to protect.
    purge_ledger(
        session,
        cycle_ids=[ids["cycle_id"]],
        product_ids=[ids["product_id"]],
    )

    session.query(OptimizationRun).filter(
        OptimizationRun.id == ids["run_id"]
    ).delete(synchronize_session=False)

    session.query(ProductionCycle).filter(
        ProductionCycle.id == ids["cycle_id"]
    ).delete(synchronize_session=False)

    session.query(Product).filter(
        Product.id == ids["product_id"]
    ).delete(synchronize_session=False)

    session.commit()
    session.close()


def _sentinel_is_intact(db, ids):
    application = db.query(ProductionApplication).filter(
        ProductionApplication.id == ids["application_id"]
    ).one_or_none()

    items = (
        db.query(ProductionApplicationItem)
        .filter(
            ProductionApplicationItem.production_application_id
            == ids["application_id"]
        )
        .all()
    )

    inventory_set = db.query(OpeningInventorySet).filter(
        OpeningInventorySet.id == ids["set_id"]
    ).one_or_none()

    opening_items = (
        db.query(OpeningInventoryItem)
        .filter(
            OpeningInventoryItem.opening_inventory_set_id
            == ids["set_id"]
        )
        .all()
    )

    return (
        application is not None
        and len(items) == 1
        and items[0].quantity_produced == Decimal("7.0000")
        and inventory_set is not None
        and len(opening_items) == 1
    )


def test_purge_with_no_scope_is_refused(db, sentinel_ledger):
    """
    The accident this signature exists to prevent: a bare
    purge_ledger(db) used to wipe both ledgers outright. It must now
    raise instead, and must not have deleted anything on the way.
    """

    with pytest.raises(ValueError, match="all_rows"):
        purge_ledger(db)

    db.expire_all()

    assert _sentinel_is_intact(db, sentinel_ledger)


def test_cycle_scoped_purge_spares_other_cycles(
    db, sentinel_ledger, optimization_cycle,
):
    """
    A purge scoped to one cycle must not reach an application in a
    different cycle - the exact confusion that made the blanket purge
    unsafe once apply started writing rows.
    """

    purge_ledger(db, cycle_ids=[optimization_cycle.id])

    db.expire_all()

    assert _sentinel_is_intact(db, sentinel_ledger)


def test_product_scoped_purge_spares_other_products(
    db, sentinel_ledger, test_products,
):
    """
    Same guarantee on the product axis, including the
    opening-inventory half: purging the fixture products' rows must
    leave the sentinel's declared opening balance and its set alone.
    """

    purge_ledger(
        db,
        product_ids=[product.id for product in test_products],
    )

    db.expire_all()

    assert _sentinel_is_intact(db, sentinel_ledger)


def test_row_owning_fixtures_leave_the_sentinel_alone(
    db, sentinel_ledger, test_products, test_resources,
    optimization_cycle, cleanup_test_data,
):
    """
    The real-world case: every row-owning fixture in conftest.py has
    now run its SETUP purge around this test. The sentinel must be
    untouched by all of them together.
    """

    db.expire_all()

    assert _sentinel_is_intact(db, sentinel_ledger)


def test_sentinel_survived_the_previous_test_teardown(
    db, sentinel_ledger,
):
    """
    The half a single test cannot prove: the previous test's fixtures
    have now TORN DOWN - test_products purging by product id,
    optimization_cycle purging by cycle id - and the sentinel must
    still be here afterwards. This test is order-dependent on the one
    above it by design; that ordering is the assertion.
    """

    db.expire_all()

    assert _sentinel_is_intact(db, sentinel_ledger)


def test_clean_slate_purge_is_still_available_and_total(db):
    """
    all_rows=True must genuinely wipe both ledgers - the clean-slate
    fixtures depend on it. Verified on a row this test owns, with the
    sentinel deliberately NOT requested, so the wipe cannot be
    mistaken for proof that scoping failed.
    """

    cycle = ProductionCycle(
        cycle_date=datetime(2027, 2, 1),
        start_date=datetime(2027, 2, 1),
        end_date=datetime(2027, 2, 8),
        status="OPEN",
    )

    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    run = OptimizationRun(
        production_cycle_id=cycle.id,
        started_at=datetime(2027, 2, 1, 9, 0),
        status="OPTIMAL",
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    application = ProductionApplication(
        application_number="PA-WIPEME",
        production_cycle_id=cycle.id,
        optimization_run_id=run.id,
        applied_at=datetime(2027, 2, 1, 9, 0, 1),
    )

    db.add(application)
    db.commit()

    try:
        purge_ledger(db, all_rows=True)

        db.expire_all()

        assert (
            db.query(ProductionApplication).count() == 0
        )
        assert db.query(ProductionApplicationItem).count() == 0
        assert db.query(OpeningInventorySet).count() == 0

    finally:
        db.query(OptimizationRun).filter(
            OptimizationRun.id == run.id
        ).delete(synchronize_session=False)

        db.query(ProductionCycle).filter(
            ProductionCycle.id == cycle.id
        ).delete(synchronize_session=False)

        db.commit()

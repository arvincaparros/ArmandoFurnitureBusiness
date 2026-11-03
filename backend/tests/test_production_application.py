from datetime import datetime
from decimal import Decimal

import pytest

from sqlalchemy.exc import IntegrityError

from app.database.models import (
    OptimizationRun,
    ProductionApplication,
    ProductionApplicationItem,
    ProductionApplicationResourceItem,
)


# `cleanup_applications` lives in conftest.py - it shares the ordered
# purge_ledger() helper with the row-owning fixtures there, so the FK
# delete order is defined once for the whole suite.


def _make_run(db, cycle_id):
    run = OptimizationRun(
        production_cycle_id=cycle_id,
        started_at=datetime(2026, 10, 30, 9, 0),
        completed_at=datetime(2026, 10, 30, 9, 0, 1),
        status="OPTIMAL",
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    return run


def test_application_persists_product_and_resource_items(
    db, cleanup_applications, optimization_cycle, test_products,
    test_resources,
):
    run = _make_run(db, optimization_cycle.id)

    application = ProductionApplication(
        application_number="PA-TEST01",
        production_cycle_id=optimization_cycle.id,
        optimization_run_id=run.id,
        applied_at=datetime(2026, 10, 30, 9, 5),
    )

    db.add(application)
    db.flush()

    db.add(
        ProductionApplicationItem(
            production_application_id=application.id,
            product_id=test_products[0].id,
            quantity_produced=Decimal("10.0000"),
        )
    )

    db.add(
        ProductionApplicationResourceItem(
            production_application_id=application.id,
            resource_id=test_resources[0].id,
            resource_name=test_resources[0].name,
            unit=test_resources[0].unit,
            consumed_quantity=Decimal("120.0000"),
        )
    )

    db.commit()
    db.refresh(application)

    assert len(application.product_items) == 1
    assert len(application.resource_items) == 1
    assert application.product_items[0].quantity_produced == (
        Decimal("10.0000")
    )
    assert application.resource_items[0].consumed_quantity == (
        Decimal("120.0000")
    )


def test_the_same_optimization_run_cannot_be_applied_twice(
    db, cleanup_applications, optimization_cycle,
):
    """
    The structural duplicate guard. Service-level checks can race;
    this constraint cannot - it is what makes "apply the same plan
    twice and get double the units" impossible rather than unlikely.
    """

    run = _make_run(db, optimization_cycle.id)

    db.add(
        ProductionApplication(
            application_number="PA-TEST02",
            production_cycle_id=optimization_cycle.id,
            optimization_run_id=run.id,
            applied_at=datetime(2026, 10, 30, 9, 5),
        )
    )
    db.commit()

    db.add(
        ProductionApplication(
            application_number="PA-TEST03",
            production_cycle_id=optimization_cycle.id,
            optimization_run_id=run.id,
            applied_at=datetime(2026, 10, 30, 9, 6),
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_two_applications_can_coexist_in_one_cycle(
    db, cleanup_applications, optimization_cycle, test_products,
):
    """
    The whole point of the ledger: the Day-1 and Day-5 applications in
    the spec's example must both survive. ProductionAllocation cannot
    express this (one row per product per cycle); this table can.
    """

    first_run = _make_run(db, optimization_cycle.id)
    second_run = _make_run(db, optimization_cycle.id)

    for index, run in enumerate((first_run, second_run), start=1):
        application = ProductionApplication(
            application_number=f"PA-TEST1{index}",
            production_cycle_id=optimization_cycle.id,
            optimization_run_id=run.id,
            applied_at=datetime(2026, 10, 30, 9, index),
        )

        db.add(application)
        db.flush()

        db.add(
            ProductionApplicationItem(
                production_application_id=application.id,
                product_id=test_products[0].id,
                quantity_produced=Decimal("10.0000"),
            )
        )

    db.commit()

    rows = (
        db.query(ProductionApplication)
        .filter(
            ProductionApplication.production_cycle_id
            == optimization_cycle.id
        )
        .all()
    )

    assert len(rows) == 2


def test_save_production_application_does_not_commit(
    db, cleanup_applications, optimization_cycle, test_products,
    test_resources,
):
    """
    Must leave the transaction open so apply_optimization can commit
    the ledger, the ProductionAllocation rows, and the utilization
    snapshot together - exactly the contract
    save_resource_utilization_history already follows.
    """

    from app.services.production_application import (
        save_production_application,
    )

    run = _make_run(db, optimization_cycle.id)

    application = save_production_application(
        db,
        optimization_cycle.id,
        run.id,
        {test_products[0].id: Decimal("10")},
        [
            {
                "resource_id": test_resources[0].id,
                "resource_name": test_resources[0].name,
                "unit": test_resources[0].unit,
                "consumed_quantity": Decimal("120"),
            }
        ],
    )

    assert application.application_number.startswith("PA-")

    db.rollback()

    assert (
        db.query(ProductionApplication)
        .filter(
            ProductionApplication.production_cycle_id
            == optimization_cycle.id
        )
        .count()
        == 0
    )


def test_cycle_aggregates_sum_across_applications(
    db, cleanup_applications, optimization_cycle, test_products,
    test_resources,
):
    """
    The spec's Day-1-plus-Day-5 example, at the aggregate level: two
    applications of 10 must read back as 20 produced for the cycle,
    and their resource consumption must add up too - that sum is what
    stops the second application re-spending the first's capacity.
    """

    from app.services.production_application import (
        get_cycle_consumed_by_resource,
        get_cycle_produced_by_product,
        get_total_produced_by_product,
        save_production_application,
    )

    for _ in range(2):
        run = _make_run(db, optimization_cycle.id)

        save_production_application(
            db,
            optimization_cycle.id,
            run.id,
            {test_products[0].id: Decimal("10")},
            [
                {
                    "resource_id": test_resources[0].id,
                    "resource_name": test_resources[0].name,
                    "unit": test_resources[0].unit,
                    "consumed_quantity": Decimal("120"),
                }
            ],
        )

        db.commit()

    produced = get_cycle_produced_by_product(
        db, optimization_cycle.id,
    )

    assert produced[test_products[0].id] == Decimal("20")

    consumed = get_cycle_consumed_by_resource(
        db, optimization_cycle.id,
    )

    assert consumed[test_resources[0].id] == Decimal("240")

    total = get_total_produced_by_product(db)

    assert total[test_products[0].id] == Decimal("20")


def test_has_application_for_run_detects_an_applied_run(
    db, cleanup_applications, optimization_cycle, test_products,
):
    from app.services.production_application import (
        has_application_for_run,
        save_production_application,
    )

    run = _make_run(db, optimization_cycle.id)

    assert has_application_for_run(db, run.id) is False

    save_production_application(
        db,
        optimization_cycle.id,
        run.id,
        {test_products[0].id: Decimal("10")},
        [],
    )
    db.commit()

    assert has_application_for_run(db, run.id) is True


def test_zero_and_negative_produced_quantities_are_skipped(
    db, cleanup_applications, optimization_cycle, test_products,
):
    """
    A plan can legitimately recommend 0 units of a product. Writing a
    zero row would add noise to the ledger without changing any
    derived figure, so it is skipped - matching apply_optimization's
    existing `if quantity <= 0: continue` rule for
    ProductionAllocation.
    """

    from app.services.production_application import (
        save_production_application,
    )

    run = _make_run(db, optimization_cycle.id)

    application = save_production_application(
        db,
        optimization_cycle.id,
        run.id,
        {
            test_products[0].id: Decimal("0"),
            test_products[1].id: Decimal("4"),
        },
        [],
    )

    db.commit()
    db.refresh(application)

    assert len(application.product_items) == 1
    assert application.product_items[0].product_id == (
        test_products[1].id
    )


def test_cycle_aggregates_are_scoped_to_their_cycle(
    db, cleanup_applications, optimization_cycle, test_products,
):
    """
    Cycle-scoped produced must reset for a new cycle while the
    all-cycles total keeps growing - that pairing is what preserves
    unsold stock across cycles.
    """

    from app.database.models import ProductionCycle
    from app.services.production_application import (
        get_cycle_produced_by_product,
        get_total_produced_by_product,
        save_production_application,
    )

    next_cycle = ProductionCycle(
        cycle_date=datetime(2026, 11, 6),
        start_date=datetime(2026, 11, 6),
        end_date=datetime(2026, 11, 13),
        status="OPEN",
    )

    db.add(next_cycle)
    db.commit()
    db.refresh(next_cycle)

    try:
        first_run = _make_run(db, optimization_cycle.id)

        save_production_application(
            db,
            optimization_cycle.id,
            first_run.id,
            {test_products[0].id: Decimal("10")},
            [],
        )
        db.commit()

        second_run = _make_run(db, next_cycle.id)

        save_production_application(
            db,
            next_cycle.id,
            second_run.id,
            {test_products[0].id: Decimal("6")},
            [],
        )
        db.commit()

        assert get_cycle_produced_by_product(
            db, next_cycle.id,
        )[test_products[0].id] == Decimal("6")

        assert get_cycle_produced_by_product(
            db, optimization_cycle.id,
        )[test_products[0].id] == Decimal("10")

        assert get_total_produced_by_product(
            db,
        )[test_products[0].id] == Decimal("16")

    finally:
        db.query(ProductionApplication).filter(
            ProductionApplication.production_cycle_id
            == next_cycle.id
        ).delete(synchronize_session=False)
        db.delete(next_cycle)
        db.commit()

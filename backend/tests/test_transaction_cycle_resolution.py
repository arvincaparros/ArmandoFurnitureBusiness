from datetime import datetime

import pytest

from app.database.models import ProductionCycle, SalesTransaction
from conftest import apply_production_to_cycle


# Task 23's gate: POST /api/transactions is refused with 409 unless a
# COMPLETE reviewed opening inventory set exists, and that check runs
# ahead of cycle resolution (Ruling 28). The two tests below that POST
# need the gate open to reach the behaviour they are actually about.
@pytest.fixture(autouse=True)
def _opening_inventory_gate(complete_opening_inventory):
    """See conftest.py::complete_opening_inventory."""


# `two_cycles` lives in conftest.py - moved there in Task 8 Step 9 so
# the transaction suites can share one cycle fixture.


def test_resolves_a_date_inside_a_cycle(db, two_cycles):
    from app.services.transaction import (
        resolve_production_cycle_for_date,
    )

    first, _ = two_cycles

    resolved = resolve_production_cycle_for_date(
        db, datetime(2026, 11, 2),
    )

    assert resolved.id == first.id


def test_start_date_is_inclusive(db, two_cycles):
    from app.services.transaction import (
        resolve_production_cycle_for_date,
    )

    first, _ = two_cycles

    assert resolve_production_cycle_for_date(
        db, datetime(2026, 10, 30),
    ).id == first.id


def test_end_date_belongs_to_the_next_cycle(db, two_cycles):
    """
    Half-open: Nov 6 is the first cycle's end_date and the second
    cycle's start_date, and must resolve to the second - otherwise
    back-to-back cycles overlap and every boundary date is ambiguous.
    """

    from app.services.transaction import (
        resolve_production_cycle_for_date,
    )

    _, second = two_cycles

    assert resolve_production_cycle_for_date(
        db, datetime(2026, 11, 6),
    ).id == second.id


def test_a_date_in_no_cycle_is_rejected(db, two_cycles):
    """
    The requirement is explicit: reject, never fall back to the latest
    cycle. A sale silently attributed to the wrong cycle corrupts that
    cycle's sold total and the stock figure derived alongside it.
    """

    from app.services.transaction import (
        resolve_production_cycle_for_date,
    )

    with pytest.raises(ValueError) as error:
        resolve_production_cycle_for_date(
            db, datetime(2027, 6, 1),
        )

    message = str(error.value).lower()

    assert "production cycle" in message
    assert "2027-06-01" in str(error.value)


def test_overlapping_cycles_are_rejected_as_ambiguous(db):
    """
    Legacy/hand-created cycles can overlap. Picking one would be the
    silent assignment the requirement forbids, so the request is
    rejected and the user is told which cycles collide.
    """

    from app.services.transaction import (
        resolve_production_cycle_for_date,
    )

    overlapping = [
        ProductionCycle(
            cycle_date=datetime(2026, 12, 1),
            start_date=datetime(2026, 12, 1),
            end_date=datetime(2026, 12, 10),
            status="OPEN",
        ),
        ProductionCycle(
            cycle_date=datetime(2026, 12, 5),
            start_date=datetime(2026, 12, 5),
            end_date=datetime(2026, 12, 15),
            status="OPEN",
        ),
    ]

    db.add_all(overlapping)
    db.commit()

    try:
        with pytest.raises(ValueError) as error:
            resolve_production_cycle_for_date(
                db, datetime(2026, 12, 7),
            )

        assert "more than one" in str(error.value).lower()

    finally:
        for cycle in overlapping:
            db.delete(cycle)

        db.commit()


def test_created_transaction_carries_its_cycle(
    client, db, two_cycles, test_products,
):
    first, _ = two_cycles

    # Stock has to exist before a sale can be recorded (Task 10 made
    # validation unconditional). Applied through the ledger, which is
    # how stock arrives in production.
    apply_production_to_cycle(db, first.id, test_products[0].id, 5)

    response = client.post(
        "/api/transactions",
        json={
            "product_id": test_products[0].id,
            "transaction_date": "2026-11-02T00:00:00",
            "quantity_produced": 5,
            "quantity": 2,
            "unit_price": 100,
            "production_cost": 0,
        },
    )

    assert response.status_code == 201
    assert response.json()["production_cycle_id"] == first.id


def test_create_rejects_a_date_outside_every_cycle(
    client, two_cycles, test_products,
):
    response = client.post(
        "/api/transactions",
        json={
            "product_id": test_products[0].id,
            "transaction_date": "2027-06-01T00:00:00",
            "quantity_produced": 5,
            "quantity": 2,
            "unit_price": 100,
            "production_cost": 0,
        },
    )

    assert response.status_code == 400
    assert "production cycle" in response.json()["detail"].lower()


def test_existing_rows_keep_a_null_cycle(db):
    """
    The column is nullable precisely so no backfill is needed: a
    pre-migration row has no reliable cycle, and inventing one would
    put fabricated numbers into a cycle's sold total. Such rows still
    count toward ALL-TIME sold (and therefore stock), just not toward
    any cycle's figures.
    """

    row = SalesTransaction(
        transaction_number="TRX-CYCLENULL",
        product_id=db.query(SalesTransaction.product_id).first()[0]
        if db.query(SalesTransaction).count()
        else 1,
        transaction_date=datetime(2020, 1, 1),
        quantity_produced=1,
        quantity=1,
        unit_price=1,
        total_sales=1,
        production_cost=0,
        unit_profit=1,
        total_profit=1,
    )

    db.add(row)
    db.commit()

    try:
        db.refresh(row)

        assert row.production_cycle_id is None

    finally:
        db.delete(row)
        db.commit()

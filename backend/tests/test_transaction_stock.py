from datetime import datetime
from decimal import Decimal

from app.database.models import (
    OpeningInventoryItem,
    OpeningInventorySet,
    OptimizationRun,
    SalesTransaction,
)
# `_apply_production` moved to conftest.py as
# apply_production_to_cycle (Task 10 Step 6) so the other
# transaction suite can use it too.
from conftest import (
    apply_production_to_cycle as _apply_production,
)


def _review_opening(
    db, product_id, quantity, suffix="A",
    effective_date=datetime(2026, 10, 1),
):
    inventory_set = OpeningInventorySet(
        set_number=f"OI-STK{suffix}",
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
            quantity=Decimal(str(quantity)),
        )
    )

    db.commit()


def _sale_payload(product_id, day, quantity, **overrides):
    payload = {
        "product_id": product_id,
        "transaction_date": f"2026-10-{day:02d}T00:00:00",
        "quantity": quantity,
        "unit_price": 100,
        "production_cost": 0,
    }
    payload.update(overrides)

    return payload


def _cleanup_sales(db, product_id):
    db.query(SalesTransaction).filter(
        SalesTransaction.product_id == product_id
    ).delete(synchronize_session=False)
    db.commit()


def test_quantity_produced_is_auto_filled_from_applied_production(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    Requirement 2: the produced figure comes from the ledger, not from
    the user. A value sent by the client is ignored rather than
    rejected, so older clients keep working while the server stays the
    only source of truth.
    """

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "B")
    _apply_production(db, transaction_cycle.id, product.id, 10)

    response = client.post(
        "/api/transactions",
        json=_sale_payload(
            product.id, 31, 4, quantity_produced=999,
        ),
    )

    assert response.status_code == 201, response.text
    assert Decimal(response.json()["quantity_produced"]) == (
        Decimal("10")
    )

    _cleanup_sales(db, product.id)


def test_a_second_sale_in_the_same_cycle_records_remaining_available_stock(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    quantity_produced now mirrors all-time available stock AT THE
    MOMENT of each sale, not a per-cycle drawdown: after apply 10 and
    a first sale of 3, available stock is 7 before the second sale
    runs, so the second sale's saved quantity_produced is 7 - not 0
    (the old anti-inflation drawdown value) and not 10 again (that
    would mean the second sale's own prior row count).
    """

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "C")
    _apply_production(db, transaction_cycle.id, product.id, 10)

    first = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 3),
    )
    second = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 2),
    )

    assert first.status_code == 201
    assert second.status_code == 201

    assert Decimal(first.json()["quantity_produced"]) == (
        Decimal("10")
    )
    assert Decimal(second.json()["quantity_produced"]) == (
        Decimal("7")
    )

    _cleanup_sales(db, product.id)


# Inverted per the Quantity Produced requirement: quantity_produced
# must now EQUAL available stock, including opening inventory - the
# opposite of this test's original premise (see
# test_a_second_sale_in_the_same_cycle_records_remaining_available_stock
# for the matching per-cycle-drawdown reversal). Same scenario,
# opposite outcome.
def test_quantity_produced_includes_opening_stock(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    With 40 units of opening stock and 6 newly produced, available
    stock before this sale is 46 - and quantity_produced must record
    46, not just the 6 newly produced this cycle.
    """

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 40, "D")
    _apply_production(db, transaction_cycle.id, product.id, 6)

    response = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 1),
    )

    assert Decimal(response.json()["quantity_produced"]) == (
        Decimal("46")
    )

    _cleanup_sales(db, product.id)


def test_a_sale_exceeding_available_stock_is_rejected(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "E")
    _apply_production(db, transaction_cycle.id, product.id, 10)

    response = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 11),
    )

    assert response.status_code == 400

    detail = response.json()["detail"].lower()

    assert "available" in detail
    assert "10" in response.json()["detail"]

    assert (
        db.query(SalesTransaction)
        .filter(SalesTransaction.product_id == product.id)
        .count()
        == 0
    )

    _cleanup_sales(db, product.id)


def test_a_sale_of_exactly_the_available_stock_succeeds(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    from app.services.inventory import (
        get_available_stock_for_product,
    )

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "F")
    _apply_production(db, transaction_cycle.id, product.id, 10)

    response = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 10),
    )

    assert response.status_code == 201

    db.expire_all()

    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("0")

    _cleanup_sales(db, product.id)


def test_the_full_day_1_3_5_scenario(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    The spec's worked example end to end: apply 10 -> stock 10;
    sell 5 -> stock 5; apply 10 again -> stock 15. This is the
    regression test for the overwrite bug that motivated the whole
    plan.
    """

    from app.services.inventory import (
        get_available_stock_for_product,
    )

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "G")

    _apply_production(db, transaction_cycle.id, product.id, 10)
    db.expire_all()
    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("10")

    assert client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 5),
    ).status_code == 201

    db.expire_all()
    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("5")

    _apply_production(db, transaction_cycle.id, product.id, 10)
    db.expire_all()
    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("15")

    _cleanup_sales(db, product.id)


# Inverted per AMENDMENT A: the plan's original version of this test
# asserted the sale was ACCEPTED (201) while no opening inventory had
# been reviewed. That soft gate is rejected - it left a window in which
# true stock could go negative, which the derived figure's zero-floor
# would then hide rather than prevent. Same scenario, opposite outcome.
def test_sales_are_refused_before_a_complete_opening_review(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    The gate from the opposite side: with no complete REVIEWED opening
    inventory the sale must be REFUSED, not recorded unvalidated.
    """

    product = test_products[0]
    _cleanup_sales(db, product.id)

    response = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 25),
    )

    assert response.status_code == 409
    assert "opening inventory" in response.json()["detail"].lower()

    # The refusal must leave nothing behind - a recorded row would be
    # exactly the unvalidated sale this gate exists to prevent.
    assert (
        db.query(SalesTransaction)
        .filter(SalesTransaction.product_id == product.id)
        .count()
        == 0
    )


def test_concurrent_sales_cannot_oversell(
    db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    Two sessions, each selling the entire stock, committed in an
    interleaved order. The product row lock must make the second one
    block until the first commits and then see the updated figure -
    without it, both read 10, both pass, and stock goes to -10.
    """

    from app.database.connection import SessionLocal
    from app.schemas.transaction import SalesTransactionCreate
    from app.services.inventory import (
        get_available_stock_for_product,
    )
    from app.services.transaction import create_transaction

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "H")
    _apply_production(db, transaction_cycle.id, product.id, 10)

    payload = SalesTransactionCreate(
        product_id=product.id,
        transaction_date=datetime(2026, 10, 31),
        quantity=Decimal("10"),
        unit_price=Decimal("100"),
        production_cost=Decimal("0"),
    )

    first_session = SessionLocal()
    second_session = SessionLocal()

    try:
        create_transaction(first_session, payload)

        # The second session now sees stock 0 and must refuse.
        try:
            create_transaction(second_session, payload)
            committed_twice = True
        except ValueError:
            committed_twice = False

        assert committed_twice is False

        db.expire_all()

        assert get_available_stock_for_product(
            db, product.id,
        ) == Decimal("0")

    finally:
        first_session.close()
        second_session.close()
        _cleanup_sales(db, product.id)


def test_raising_a_sale_above_available_stock_is_rejected(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    The update path needs the same guard as create: editing 4 up to 20
    oversells just as surely as recording 20 in the first place.
    """

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "I")
    _apply_production(db, transaction_cycle.id, product.id, 10)

    created = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 4),
    ).json()

    response = client.patch(
        f"/api/transactions/{created['id']}",
        json={"quantity": 20},
    )

    assert response.status_code == 400
    assert "available" in response.json()["detail"].lower()

    db.expire_all()

    assert db.get(
        SalesTransaction, created["id"],
    ).quantity == Decimal("4.0000")

    _cleanup_sales(db, product.id)


def test_an_update_does_not_double_count_its_own_quantity(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    The row being edited already counts against stock, so its own
    current quantity must be added back before the proposed quantity is
    checked. Without that, raising 4 to 10 against 10 units of
    production looks like a demand for 14 and is wrongly rejected.
    """

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "J")
    _apply_production(db, transaction_cycle.id, product.id, 10)

    created = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 4),
    ).json()

    response = client.patch(
        f"/api/transactions/{created['id']}",
        json={"quantity": 10},
    )

    assert response.status_code == 200, response.text

    db.expire_all()

    from app.services.inventory import (
        get_available_stock_for_product,
    )

    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("0")

    _cleanup_sales(db, product.id)


def test_lowering_a_sale_returns_stock(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    from app.services.inventory import (
        get_available_stock_for_product,
    )

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "K")
    _apply_production(db, transaction_cycle.id, product.id, 10)

    created = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 10),
    ).json()

    assert client.patch(
        f"/api/transactions/{created['id']}",
        json={"quantity": 3},
    ).status_code == 200

    db.expire_all()

    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("7")

    _cleanup_sales(db, product.id)


def test_deleting_a_sale_returns_stock(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    No code change needed - stock is derived, so removing the row
    removes its deduction automatically. Pinned because a stored
    counter would have silently got this wrong, and this test is what
    proves the derived design is doing its job.
    """

    from app.services.inventory import (
        get_available_stock_for_product,
    )

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "L")
    _apply_production(db, transaction_cycle.id, product.id, 10)

    created = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 6),
    ).json()

    assert client.delete(
        f"/api/transactions/{created['id']}",
    ).status_code == 204

    db.expire_all()

    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("10")

    _cleanup_sales(db, product.id)


def test_editing_a_zero_produced_row_does_not_crash(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    update_transaction reconstructs the per-unit production cost by
    dividing the stored total by quantity_produced, guarded by
    `elif transaction.quantity_produced:` precisely because a stored
    0 is still possible - a legacy row, or one edited directly - even
    though create_transaction itself can no longer save one (a
    successful sale always implies pre-sale available stock > 0, so
    quantity_produced is now always positive going forward). Built
    directly rather than via two sales in a cycle, since that no
    longer produces a 0 under the current create-time rule.
    """

    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "M")
    _apply_production(db, transaction_cycle.id, product.id, 10)

    zero_produced_row = SalesTransaction(
        transaction_number="TRX-ZEROPROD",
        product_id=product.id,
        production_cycle_id=transaction_cycle.id,
        transaction_date=datetime(2026, 10, 31),
        quantity=Decimal("2"),
        quantity_produced=Decimal("0"),
        unit_price=Decimal("100.00"),
        total_sales=Decimal("200.00"),
        production_cost=Decimal("0.00"),
        unit_profit=Decimal("100.0000"),
        total_profit=Decimal("200.0000"),
    )

    db.add(zero_produced_row)
    db.commit()
    db.refresh(zero_produced_row)

    response = client.patch(
        f"/api/transactions/{zero_produced_row.id}",
        json={"quantity": 1},
    )

    assert response.status_code == 200, response.text
    assert Decimal(response.json()["production_cost"]) == (
        Decimal("0.00")
    )

    _cleanup_sales(db, product.id)


def test_moving_a_sale_to_a_date_outside_every_cycle_succeeds_as_null(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    A Production Cycle is no longer a precondition for recording or
    editing a sale. Moving a transaction's date to one no cycle
    covers must succeed and clear its cycle attribution to None,
    not be rejected.
    """

    product = test_products[0]
    _cleanup_sales(db, product.id)
    # Same setup as every other sale-POSTing test here: the sale is
    # refused outright without a complete reviewed opening balance,
    # and needs stock to exist before it can be recorded.
    _review_opening(db, product.id, 0, "M")
    _apply_production(db, transaction_cycle.id, product.id, 5)

    created = client.post(
        "/api/transactions",
        json=_sale_payload(product.id, 31, 1),
    ).json()

    assert created["production_cycle_id"] == transaction_cycle.id

    response = client.patch(
        f"/api/transactions/{created['id']}",
        json={"transaction_date": "2029-01-01T00:00:00"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["production_cycle_id"] is None

    _cleanup_sales(db, product.id)


def test_editing_a_pre_rollout_row_leaves_it_unattributed(
    client, db, cleanup_opening_inventory, test_products,
):
    """
    production_cycle_id IS NULL is the legacy marker the forecast's
    production series reads (see services/forecasting.py). An edit
    to a pre-rollout row must not claim it for a cycle, or its
    stored produced figure would vanish from the chart.

    A reviewed opening balance is established first because editing a
    sale is a stock-affecting operation and is refused without one
    (AMENDMENT A, closing R-23b). That is orthogonal to what this test
    asserts - the legacy row must still come back unattributed.
    """

    from app.services.transaction import update_transaction
    from app.schemas.transaction import SalesTransactionUpdate
    from app.database.models import SalesTransaction

    product = test_products[0]
    _review_opening(db, product.id, 0, "N")

    legacy = SalesTransaction(
        transaction_number="TRX-LEG001",
        product_id=product.id,
        production_cycle_id=None,
        transaction_date=datetime(2026, 8, 23),
        quantity=Decimal("1"),
        quantity_produced=Decimal("5"),
        unit_price=Decimal("100.00"),
        total_sales=Decimal("100.00"),
        production_cost=Decimal("0.00"),
        unit_profit=Decimal("0.00"),
        total_profit=Decimal("0.00"),
    )

    db.add(legacy)
    db.commit()
    db.refresh(legacy)

    try:
        updated = update_transaction(
            db,
            legacy,
            SalesTransactionUpdate(
                transaction_date=datetime(2026, 8, 24),
            ),
        )

        assert updated.production_cycle_id is None
        assert updated.quantity_produced == Decimal("5")

    finally:
        db.delete(legacy)
        db.commit()


# --- Cross-cycle quantity_produced (the PA-0001 / Cycle 939 bug) -----------
#
# Reproduces the real scenario that motivated this fix: production
# applied under one cycle, a sale recorded under a DIFFERENT, later
# cycle created afterward to cover today's date. quantity_produced
# must reflect all-time available stock across both cycles, not only
# production applied within the sale's own resolved cycle.


def test_production_in_one_cycle_and_sale_in_a_later_cycle(
    client, db, cleanup_opening_inventory, cleanup_applications,
    two_cycles, test_products,
):
    first, second = two_cycles
    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "P")

    # All production lives in the FIRST cycle only - second has none.
    _apply_production(db, first.id, product.id, 5)

    # This date resolves to the SECOND cycle (Nov 6-13), a cycle with
    # zero production of its own.
    response = client.post(
        "/api/transactions",
        json={
            "product_id": product.id,
            "transaction_date": "2026-11-07T00:00:00",
            "quantity": 2,
            "unit_price": 100,
            "production_cost": 0,
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["production_cycle_id"] == second.id

    # quantity_produced equals available stock AT THE MOMENT of
    # creation (opening 0 + produced 5 from the first cycle - sold 0
    # so far = 5) - not the second cycle's own (empty) production,
    # which is what previously saved 0 despite 5 units being
    # genuinely available.
    assert Decimal(response.json()["quantity_produced"]) == (
        Decimal("5")
    )

    db.expire_all()

    from app.services.inventory import (
        get_available_stock_for_product,
    )

    # Available stock correctly decreases after the sale, all-time,
    # regardless of which cycle the sale landed in.
    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("3")

    _cleanup_sales(db, product.id)


def test_multiple_applications_across_different_cycles_accumulate(
    client, db, cleanup_opening_inventory, cleanup_applications,
    two_cycles, test_products,
):
    """
    Production applied in two SEPARATE cycles must both count toward
    the same all-time balance - accumulating, never one cycle's
    application overwriting or shadowing the other's.
    """

    first, second = two_cycles
    product = test_products[0]
    _cleanup_sales(db, product.id)
    _review_opening(db, product.id, 0, "Q")

    _apply_production(db, first.id, product.id, 5)
    _apply_production(db, second.id, product.id, 4)

    db.expire_all()

    from app.services.inventory import (
        get_available_stock_for_product,
    )

    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("9")

    # A sale recorded against the second cycle must auto-fill from
    # the combined 9, not just the second cycle's own 4.
    response = client.post(
        "/api/transactions",
        json={
            "product_id": product.id,
            "transaction_date": "2026-11-07T00:00:00",
            "quantity": 1,
            "unit_price": 100,
            "production_cost": 0,
        },
    )

    assert response.status_code == 201, response.text
    assert Decimal(response.json()["quantity_produced"]) == (
        Decimal("9")
    )

    db.expire_all()

    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("8")

    _cleanup_sales(db, product.id)


def test_oversell_validation_ignores_sales_before_ledger_effective_date(
    client, db, cleanup_opening_inventory, cleanup_applications,
    transaction_cycle, test_products,
):
    """
    Thesis-scope simplification: a historical sale recorded before the
    ledger's effective date must not count against the figure used to
    validate a NEW sale. Without scoping, the pre-ledger sale below
    would read available stock as 10 - 8 = 2 and reject a sale of 10;
    with scoping it is excluded entirely, so the full 10 remain
    sellable.
    """

    product = test_products[0]
    _cleanup_sales(db, product.id)

    effective_date = datetime(2026, 10, 1)
    _review_opening(
        db, product.id, 0, "R", effective_date=effective_date,
    )
    _apply_production(db, transaction_cycle.id, product.id, 10)

    pre_ledger_sale = SalesTransaction(
        transaction_number="TRX-STKPRE",
        product_id=product.id,
        production_cycle_id=None,
        transaction_date=datetime(2026, 9, 1),
        quantity_produced=Decimal("0"),
        quantity=Decimal("8"),
        unit_price=Decimal("100"),
        total_sales=Decimal("800"),
        production_cost=Decimal("0"),
        unit_profit=Decimal("100"),
        total_profit=Decimal("800"),
    )

    db.add(pre_ledger_sale)
    db.commit()

    try:
        response = client.post(
            "/api/transactions",
            json=_sale_payload(product.id, 31, 10),
        )

        assert response.status_code == 201, response.text
        assert Decimal(response.json()["quantity_produced"]) == (
            Decimal("10")
        )

    finally:
        db.delete(pre_ledger_sale)
        db.commit()
        _cleanup_sales(db, product.id)

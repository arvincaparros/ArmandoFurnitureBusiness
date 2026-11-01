"""
Task 23 — the complete-opening-inventory gate.

Completeness means "every ACTIVE product that existed on the set's
effective_date carries an explicit opening quantity, including zero".
These tests pin an effective_date EARLIER than every product already
seeded in armando_furniture_test, then create their own products with
an explicit created_at on either side of it. That keeps each case about
one rule rather than about the 23 products the test database happens to
carry.

Kept in its own module rather than appended to test_opening_inventory.py
because these tests need products with a controlled `created_at`, which
no shared fixture provides.
"""

from datetime import datetime
from decimal import Decimal

from app.database.models import (
    OpeningInventoryItem,
    OpeningInventorySet,
    Product,
    SalesTransaction,
)


def _product(db, name, created_at, is_active=True):
    product = Product(
        name=name,
        selling_price=Decimal("100.00"),
        labor_cost=Decimal("0.00"),
        is_active=is_active,
        created_at=created_at,
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    return product


def _draft(db, effective_date, declared=()):
    inventory_set = OpeningInventorySet(
        set_number="OI-T23-" + datetime.utcnow().strftime("%H%M%S%f"),
        status="DRAFT",
        effective_date=effective_date,
    )

    db.add(inventory_set)
    db.flush()

    for product_id, quantity in declared:
        db.add(
            OpeningInventoryItem(
                opening_inventory_set_id=inventory_set.id,
                product_id=product_id,
                quantity=Decimal(quantity),
            )
        )

    db.commit()
    db.refresh(inventory_set)

    return inventory_set


def _cleanup(db, product_ids):
    db.rollback()

    db.query(OpeningInventoryItem).filter(
        OpeningInventoryItem.product_id.in_(product_ids)
    ).delete(synchronize_session=False)

    db.query(Product).filter(
        Product.id.in_(product_ids)
    ).delete(synchronize_session=False)

    db.commit()


def test_review_refuses_a_set_missing_an_applicable_product(
    client, db, cleanup_opening_inventory,
):
    """
    The core of the gate: an ACTIVE product that existed on the
    effective date and carries no explicit quantity makes the set
    incomplete, and the refusal must NAME it so the user knows what is
    still needed.
    """

    required = _product(
        db, "T23 Required Product", datetime(2025, 6, 1),
    )
    declared = _product(
        db, "T23 Declared Product", datetime(2025, 6, 2),
    )

    inventory_set = _draft(
        db, datetime(2026, 1, 1), declared=[(declared.id, "5")],
    )

    try:
        response = client.post(
            f"/api/opening-inventory/{inventory_set.id}/review",
        )

        assert response.status_code == 400
        assert "T23 Required Product" in response.json()["detail"]

        db.expire_all()
        assert db.get(
            OpeningInventorySet, inventory_set.id,
        ).status == "DRAFT"

    finally:
        _cleanup(db, [required.id, declared.id])


def test_an_explicit_zero_counts_as_a_declaration(
    client, db, cleanup_opening_inventory,
):
    """
    The distinction the whole gate rests on: zero DECLARED is complete,
    zero OMITTED is not. A missing row is never an implied zero.
    """

    product = _product(
        db, "T23 Zero Product", datetime(2025, 6, 3),
    )

    inventory_set = _draft(
        db, datetime(2026, 1, 1), declared=[(product.id, "0")],
    )

    try:
        response = client.post(
            f"/api/opening-inventory/{inventory_set.id}/review",
        )

        assert response.status_code == 200
        assert response.json()["status"] == "REVIEWED"

    finally:
        _cleanup(db, [product.id])


def test_a_product_created_after_the_effective_date_is_not_required(
    client, db, cleanup_opening_inventory,
):
    """
    The A.1 ruling, enforced: a product that did not exist on the
    effective date cannot have had opening stock, so it opens at zero
    BY CONSTRUCTION and must not block review. Without this, adding any
    product would freeze every sale until someone reviewed a new set.
    """

    existing = _product(
        db, "T23 Existing Product", datetime(2025, 6, 4),
    )
    later = _product(
        db, "T23 Later Product", datetime(2026, 6, 1),
    )

    inventory_set = _draft(
        db, datetime(2026, 1, 1), declared=[(existing.id, "2")],
    )

    try:
        response = client.post(
            f"/api/opening-inventory/{inventory_set.id}/review",
        )

        assert response.status_code == 200

    finally:
        _cleanup(db, [existing.id, later.id])


def test_an_inactive_product_is_not_required(
    client, db, cleanup_opening_inventory,
):
    """
    The other half of the A.1 ruling. Product deletion is a soft
    delete, so retired products would otherwise block review forever on
    historical clutter.
    """

    active = _product(
        db, "T23 Active Product", datetime(2025, 6, 5),
    )
    retired = _product(
        db, "T23 Retired Product", datetime(2025, 6, 6),
        is_active=False,
    )

    inventory_set = _draft(
        db, datetime(2026, 1, 1), declared=[(active.id, "1")],
    )

    try:
        response = client.post(
            f"/api/opening-inventory/{inventory_set.id}/review",
        )

        assert response.status_code == 200

    finally:
        _cleanup(db, [active.id, retired.id])


def test_a_sale_is_refused_with_409_before_a_complete_review(
    client, db, cleanup_opening_inventory, test_products,
):
    """
    The inversion of the rejected soft gate. With no complete REVIEWED
    opening inventory the sale must be REFUSED - accepting it
    unvalidated is exactly what would let true stock go negative during
    setup, which the derived figure's zero-floor would then hide rather
    than prevent.
    """

    response = client.post(
        "/api/transactions",
        json={
            "product_id": test_products[0].id,
            "transaction_date": "2026-10-31",
            "quantity_produced": 5,
            "quantity": 2,
            "unit_price": "100.00",
            "production_cost": "10.00",
        },
    )

    assert response.status_code == 409
    assert "opening inventory" in response.json()["detail"].lower()

    assert (
        db.query(SalesTransaction)
        .filter(SalesTransaction.product_id == test_products[0].id)
        .count()
        == 0
    )


def test_a_sale_is_accepted_once_a_complete_set_is_reviewed(
    client, db, cleanup_opening_inventory, test_products, two_cycles,
):
    """
    The gate opens. Same request, same product - the only thing that
    changed is that a complete opening balance now exists.

    two_cycles is required since Task 8: a sale whose date falls in no
    production cycle is rejected with 400, and Oct 31 sits inside the
    first of those two cycles. The sibling test above needs no cycle
    because the opening-inventory gate is checked BEFORE cycle
    resolution (Ruling 28), so it still gets its 409.
    """

    # Declares 5 units of opening stock, not 0: Task 10 made stock
    # validation unconditional, so a sale of 2 against a declared 0
    # would now be rejected for lack of stock rather than accepted.
    # The point of this test is that the GATE opens, so the product
    # needs something to sell.
    inventory_set = _draft(
        db,
        datetime(2026, 1, 1),
        declared=[(test_products[0].id, "5")],
    )

    assert client.post(
        f"/api/opening-inventory/{inventory_set.id}/review",
    ).status_code == 200

    try:
        response = client.post(
            "/api/transactions",
            json={
                "product_id": test_products[0].id,
                "transaction_date": "2026-10-31",
                "quantity_produced": 5,
                "quantity": 2,
                "unit_price": "100.00",
                "production_cost": "10.00",
            },
        )

        assert response.status_code == 201

    finally:
        db.rollback()
        db.query(SalesTransaction).filter(
            SalesTransaction.product_id == test_products[0].id
        ).delete(synchronize_session=False)
        db.commit()

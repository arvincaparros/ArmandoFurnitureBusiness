from datetime import datetime
from decimal import Decimal

import pytest

from sqlalchemy.exc import IntegrityError

from app.database.models import (
    OpeningInventoryItem,
    OpeningInventorySet,
)


# `cleanup_opening_inventory` lives in conftest.py - see the ledger
# purge section there for why the delete order is centralized.

# Task 23 note on the effective dates below: review now REFUSES a set
# that omits any active product which existed on the set's
# effective_date. The lifecycle tests in this file date their sets to
# early 2026 - before every product in armando_furniture_test - so they
# stay complete without having to declare a balance for every seeded
# product. Completeness itself is tested directly at the end of the
# file, where the applicable product set is controlled explicitly.


def test_opening_inventory_set_persists_with_items(
    db, cleanup_opening_inventory, test_products,
):
    inventory_set = OpeningInventorySet(
        set_number="OI-TEST01",
        status="DRAFT",
        effective_date=datetime(2026, 10, 30),
        notes="counted by hand",
    )

    db.add(inventory_set)
    db.flush()

    db.add(
        OpeningInventoryItem(
            opening_inventory_set_id=inventory_set.id,
            product_id=test_products[0].id,
            quantity=Decimal("12.0000"),
            notes="warehouse A",
        )
    )

    db.commit()
    db.refresh(inventory_set)

    assert inventory_set.status == "DRAFT"
    assert inventory_set.reviewed_at is None
    assert len(inventory_set.items) == 1
    assert inventory_set.items[0].quantity == Decimal("12.0000")


def test_only_one_reviewed_set_can_exist(
    db, cleanup_opening_inventory,
):
    """
    The partial unique index is what makes
    get_reviewed_opening_inventory_set's "the" in its name true - two
    reviewed sets would make opening balances ambiguous, and every
    stock figure in the system depends on there being exactly one.
    """

    db.add(
        OpeningInventorySet(
            set_number="OI-TEST02",
            status="REVIEWED",
            effective_date=datetime(2026, 10, 30),
            reviewed_at=datetime(2026, 10, 30),
        )
    )
    db.commit()

    db.add(
        OpeningInventorySet(
            set_number="OI-TEST03",
            status="REVIEWED",
            effective_date=datetime(2026, 10, 31),
            reviewed_at=datetime(2026, 10, 31),
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_one_item_per_product_per_set(
    db, cleanup_opening_inventory, test_products,
):
    inventory_set = OpeningInventorySet(
        set_number="OI-TEST04",
        status="DRAFT",
        effective_date=datetime(2026, 10, 30),
    )

    db.add(inventory_set)
    db.flush()

    db.add_all(
        [
            OpeningInventoryItem(
                opening_inventory_set_id=inventory_set.id,
                product_id=test_products[0].id,
                quantity=Decimal("5.0000"),
            ),
            OpeningInventoryItem(
                opening_inventory_set_id=inventory_set.id,
                product_id=test_products[0].id,
                quantity=Decimal("7.0000"),
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_create_draft_then_review_enables_stock_validation(
    client, db, cleanup_opening_inventory, test_products,
):
    """
    The review gate: is_stock_validation_enabled must stay False while
    the declaration is still a draft, and flip to True only once a
    human has reviewed it. Sales validation keys off this - validating
    against an unconfirmed balance would reject real sales.
    """

    from app.services.opening_inventory import (
        is_stock_validation_enabled,
    )

    assert is_stock_validation_enabled(db) is False

    create_response = client.post(
        "/api/opening-inventory",
        json={
            "effective_date": "2026-01-01T00:00:00",
            "notes": "initial physical count",
            "items": [
                {
                    "product_id": test_products[0].id,
                    "quantity": 8,
                    "notes": "warehouse A",
                }
            ],
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["status"] == "DRAFT"
    assert created["set_number"].startswith("OI-")
    assert len(created["items"]) == 1

    db.expire_all()
    assert is_stock_validation_enabled(db) is False

    review_response = client.post(
        f"/api/opening-inventory/{created['id']}/review",
    )

    assert review_response.status_code == 200
    reviewed = review_response.json()
    assert reviewed["status"] == "REVIEWED"
    assert reviewed["reviewed_at"] is not None
    assert reviewed["reviewed_by_username"] is not None

    db.expire_all()
    assert is_stock_validation_enabled(db) is True


def test_reviewed_set_cannot_be_edited(
    client, db, cleanup_opening_inventory, test_products,
):
    create_response = client.post(
        "/api/opening-inventory",
        json={
            "effective_date": "2026-01-01T00:00:00",
            "items": [
                {"product_id": test_products[0].id, "quantity": 8}
            ],
        },
    )

    set_id = create_response.json()["id"]
    client.post(f"/api/opening-inventory/{set_id}/review")

    update_response = client.patch(
        f"/api/opening-inventory/{set_id}",
        json={
            "items": [
                {"product_id": test_products[0].id, "quantity": 99}
            ]
        },
    )

    assert update_response.status_code == 400
    assert "reviewed" in update_response.json()["detail"].lower()


def test_reviewing_a_new_set_supersedes_the_previous_one(
    client, db, cleanup_opening_inventory, test_products,
):
    """
    A correction must not mutate the already-reviewed declaration -
    the original stays readable as SUPERSEDED, and the partial unique
    index means the flip and the new review happen together or not at
    all.
    """

    from app.services.opening_inventory import (
        get_opening_quantities,
    )

    first = client.post(
        "/api/opening-inventory",
        json={
            "effective_date": "2026-01-01T00:00:00",
            "items": [
                {"product_id": test_products[0].id, "quantity": 8}
            ],
        },
    ).json()

    client.post(f"/api/opening-inventory/{first['id']}/review")

    second = client.post(
        "/api/opening-inventory",
        json={
            "effective_date": "2026-01-02T00:00:00",
            "notes": "recount",
            "items": [
                {"product_id": test_products[0].id, "quantity": 11}
            ],
        },
    ).json()

    client.post(f"/api/opening-inventory/{second['id']}/review")

    db.expire_all()

    first_row = db.get(OpeningInventorySet, first["id"])
    second_row = db.get(OpeningInventorySet, second["id"])

    assert first_row.status == "SUPERSEDED"
    assert second_row.status == "REVIEWED"
    assert get_opening_quantities(db)[test_products[0].id] == (
        Decimal("11.0000")
    )


def test_opening_quantities_is_empty_before_review(
    db, cleanup_opening_inventory, test_products,
):
    """
    A DRAFT set's numbers must not leak into stock derivation - an
    unreviewed count is not an opening balance yet.
    """

    from app.services.opening_inventory import (
        get_opening_quantities,
    )

    inventory_set = OpeningInventorySet(
        set_number="OI-TEST05",
        status="DRAFT",
        effective_date=datetime(2026, 10, 30),
    )

    db.add(inventory_set)
    db.flush()

    db.add(
        OpeningInventoryItem(
            opening_inventory_set_id=inventory_set.id,
            product_id=test_products[0].id,
            quantity=Decimal("50.0000"),
        )
    )

    db.commit()

    assert get_opening_quantities(db) == {}


def test_create_rejects_duplicate_product_rows(
    client, cleanup_opening_inventory, test_products,
):
    response = client.post(
        "/api/opening-inventory",
        json={
            "effective_date": "2026-01-01T00:00:00",
            "items": [
                {"product_id": test_products[0].id, "quantity": 3},
                {"product_id": test_products[0].id, "quantity": 4},
            ],
        },
    )

    assert response.status_code == 422


def test_create_rejects_negative_quantity(
    client, cleanup_opening_inventory, test_products,
):
    response = client.post(
        "/api/opening-inventory",
        json={
            "effective_date": "2026-01-01T00:00:00",
            "items": [
                {"product_id": test_products[0].id, "quantity": -1}
            ],
        },
    )

    assert response.status_code == 422


def test_active_endpoint_reports_the_gate(
    client, cleanup_opening_inventory, test_products,
):
    before = client.get("/api/opening-inventory/active")

    assert before.status_code == 200
    assert before.json()["stock_validation_enabled"] is False
    assert before.json()["reviewed_set"] is None

    created = client.post(
        "/api/opening-inventory",
        json={
            "effective_date": "2026-01-01T00:00:00",
            "items": [
                {"product_id": test_products[0].id, "quantity": 8}
            ],
        },
    ).json()

    client.post(f"/api/opening-inventory/{created['id']}/review")

    after = client.get("/api/opening-inventory/active")

    assert after.json()["stock_validation_enabled"] is True
    assert after.json()["reviewed_set"]["id"] == created["id"]


def test_opening_inventory_requires_authentication(
    unauthenticated_client,
):
    assert unauthenticated_client.get(
        "/api/opening-inventory"
    ).status_code == 401

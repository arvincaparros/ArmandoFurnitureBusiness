from datetime import datetime
from decimal import Decimal

import pytest

from app.database.models import (
    OpeningInventoryItem,
    OpeningInventorySet,
    Product,
    SalesTransaction,
)
from app.services.transaction import calculate_transaction_values
from conftest import apply_production_to_cycle, purge_ledger


@pytest.fixture(autouse=True)
def _opening_inventory_gate(complete_opening_inventory):
    """
    Task 23: POST /api/transactions is refused with 409 unless a
    COMPLETE reviewed opening inventory set exists. Every test in
    this module predates that gate, so one is established for all
    of them rather than threaded through nine call sites.

    The set itself lives in conftest.py as
    complete_opening_inventory - shared since Task 8's cycle
    resolution tests need the same precondition.
    """


def create_test_product(db):
    product = Product(
        name="Transaction Test Product",
        selling_price=Decimal("3500.00"),
        is_active=True,
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    return product


def test_create_transaction(client, db, two_cycles):
    product = create_test_product(db)

    # quantity_produced is server-computed now, and a sale
    # needs stock to exist. Applying exactly 6 units makes
    # the auto-filled figure equal the 6 this test used to
    # submit, so every assertion below is unchanged.
    apply_production_to_cycle(
        db, two_cycles[0].id, product.id, 6,
    )

    response = client.post(
        "/api/transactions",
        json={
            "product_id": product.id,
            "transaction_date": "2026-11-02T10:00:00",
            "quantity_produced": "6",
            "quantity": "5",
            "unit_price": "3200.00",
            "production_cost": "3000.00",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["product_id"] == product.id
    assert data["transaction_number"].startswith("TRX-")
    assert Decimal(data["quantity_produced"]) == Decimal("6")
    assert Decimal(data["quantity"]) == Decimal("5")
    assert Decimal(data["unit_price"]) == Decimal("3200.00")
    # production_cost in the request is PER-UNIT (3000); the stored/
    # returned value is the TOTAL: quantity_produced (6) x 3000.
    assert Decimal(data["production_cost"]) == Decimal("18000.00")
    assert Decimal(data["total_sales"]) == Decimal("16000.00")
    assert Decimal(data["unit_profit"]) == Decimal("-400.0000")
    assert Decimal(data["total_profit"]) == Decimal("-2000.0000")

    # Scoped purge first: this test applied production for this
    # product, and production_application_items.product_id is
    # RESTRICT, so the product cannot be deleted until its own
    # ledger rows are gone. Scoped to this product only.
    purge_ledger(db, product_ids=[product.id])

    db.delete(product)
    db.commit()


def test_create_transaction_product_not_found(client):
    response = client.post(
        "/api/transactions",
        json={
            "product_id": 999999,
            "transaction_date": "2026-11-02T10:00:00",
            "quantity_produced": "6",
            "quantity": "5",
            "unit_price": "3200.00",
            "production_cost": "3000.00",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Product not found"


def test_create_transaction_inactive_product(client, db):
    product = Product(
        name="Inactive Transaction Product",
        selling_price=Decimal("3500.00"),
        is_active=False,
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    response = client.post(
        "/api/transactions",
        json={
            "product_id": product.id,
            "transaction_date": "2026-11-02T10:00:00",
            "quantity_produced": "6",
            "quantity": "5",
            "unit_price": "3200.00",
            "production_cost": "3000.00",
        },
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Cannot create transaction for inactive product"
    )

    db.delete(product)
    db.commit()


def test_get_transactions(client, db):
    product = create_test_product(db)

    transaction = SalesTransaction(
        transaction_number="TRX-TEST-001",
        product_id=product.id,
        transaction_date=datetime(2026, 8, 10, 10, 0),
        quantity_produced=Decimal("6"),
        quantity=Decimal("5"),
        unit_price=Decimal("3200.00"),
        total_sales=Decimal("16000.00"),
        production_cost=Decimal("3000.00"),
        unit_profit=Decimal("2600.0000"),
        total_profit=Decimal("13000.0000"),
    )

    db.add(transaction)
    db.commit()

    # show_all=true because this test only cares that the endpoint
    # returns the row it just inserted. Without it the endpoint
    # applies its default window (the 7 most recent distinct
    # transaction dates), which depends on whatever else is in the
    # shared table at the time. The window rules themselves are
    # covered exhaustively in test_transaction_date_filter.py, which
    # owns the table and can assert exact counts.
    response = client.get(
        "/api/transactions",
        params={"show_all": "true"},
    )

    assert response.status_code == 200

    data = response.json()["items"]

    assert any(
        item["id"] == transaction.id
        for item in data
    )

    db.delete(transaction)
    db.delete(product)
    db.commit()


def test_get_transaction(client, db):
    product = create_test_product(db)

    transaction = SalesTransaction(
        transaction_number="TRX-TEST-002",
        product_id=product.id,
        transaction_date=datetime(2026, 8, 10, 10, 0),
        quantity_produced=Decimal("6"),
        quantity=Decimal("5"),
        unit_price=Decimal("3200.00"),
        total_sales=Decimal("16000.00"),
        production_cost=Decimal("3000.00"),
        unit_profit=Decimal("2600.0000"),
        total_profit=Decimal("13000.0000"),
    )

    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    response = client.get(
        f"/api/transactions/{transaction.id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == transaction.id
    assert data["product_id"] == product.id
    assert data["transaction_number"] == "TRX-TEST-002"
    assert Decimal(data["quantity_produced"]) == Decimal("6")
    assert Decimal(data["quantity"]) == Decimal("5")
    assert Decimal(data["production_cost"]) == Decimal("3000.00")

    db.delete(transaction)
    db.delete(product)
    db.commit()


def test_get_transaction_not_found(client):
    response = client.get(
        "/api/transactions/999999"
    )

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "Sales transaction not found"
    )


def test_update_transaction_recalculates_totals(
    client, db, two_cycles,
):
    product = create_test_product(db)

    # Task 10/11 made stock validation unconditional, and this test
    # raises the sold quantity from 5 to 10 - so 10 units have to
    # exist. Applied through the ledger, which also leaves this row's
    # production_cycle_id NULL (the PATCH below never touches
    # transaction_date, so the legacy marker is preserved).
    apply_production_to_cycle(db, two_cycles[0].id, product.id, 20)

    transaction = SalesTransaction(
        transaction_number="TRX-TEST-003",
        product_id=product.id,
        transaction_date=datetime(2026, 8, 10, 10, 0),
        quantity_produced=Decimal("6"),
        quantity=Decimal("5"),
        unit_price=Decimal("3200.00"),
        total_sales=Decimal("16000.00"),
        production_cost=Decimal("3000.00"),
        unit_profit=Decimal("2600.0000"),
        total_profit=Decimal("13000.0000"),
    )

    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    response = client.patch(
        f"/api/transactions/{transaction.id}",
        json={
            "quantity": "10",
            "unit_price": "3000.00",
            "production_cost": "5000.00",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert Decimal(data["quantity"]) == Decimal("10")
    assert Decimal(data["unit_price"]) == Decimal("3000.00")
    # production_cost in the PATCH is PER-UNIT (5000); quantity_produced
    # is unchanged (6), so the stored/returned total is 6 x 5000.
    assert Decimal(data["production_cost"]) == Decimal("30000.00")
    assert Decimal(data["total_sales"]) == Decimal("30000.00")
    assert Decimal(data["unit_profit"]) == Decimal("0.0000")
    assert Decimal(data["total_profit"]) == Decimal("0.0000")

    db.delete(transaction)
    db.commit()

    # Scoped purge: the applied production above references this
    # product, and production_application_items.product_id is RESTRICT.
    purge_ledger(db, product_ids=[product.id])

    db.delete(product)
    db.commit()


def test_delete_transaction(client, db):
    product = create_test_product(db)

    transaction = SalesTransaction(
        transaction_number="TRX-TEST-004",
        product_id=product.id,
        transaction_date=datetime(2026, 8, 10, 10, 0),
        quantity_produced=Decimal("6"),
        quantity=Decimal("5"),
        unit_price=Decimal("3200.00"),
        total_sales=Decimal("16000.00"),
        production_cost=Decimal("3000.00"),
        unit_profit=Decimal("2600.0000"),
        total_profit=Decimal("13000.0000"),
    )

    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    transaction_id = transaction.id

    response = client.delete(
        f"/api/transactions/{transaction_id}"
    )

    assert response.status_code == 204

    db.expire_all()

    assert db.get(
        SalesTransaction,
        transaction_id,
    ) is None

    db.delete(product)
    db.commit()


def test_create_transaction_rejects_invalid_quantity(client, db):
    product = create_test_product(db)

    response = client.post(
        "/api/transactions",
        json={
            "product_id": product.id,
            "transaction_date": "2026-11-02T10:00:00",
            "quantity": "0",
            "unit_price": "3200.00",
            "unit_profit": "800.0000",
        },
    )

    assert response.status_code == 422

    db.delete(product)
    db.commit()

def test_create_transaction_ignores_a_client_sent_quantity_produced(
    client, db, two_cycles, test_products,
):
    """
    Replaces test_create_transaction_rejects_invalid_quantity_produced.
    quantity_produced is server-computed now (see
    app/schemas/transaction.py::SalesTransactionCreate), so a
    client-sent value must be IGNORED rather than rejected - existing
    callers keep working, and the old "reject a non-positive value"
    contract no longer applies because the client no longer owns the
    field.
    """

    first, _ = two_cycles

    apply_production_to_cycle(db, first.id, test_products[0].id, 3)

    response = client.post(
        "/api/transactions",
        json={
            "product_id": test_products[0].id,
            "transaction_date": "2026-11-02T00:00:00",
            "quantity_produced": 0,
            "quantity": 1,
            "unit_price": 100,
            "production_cost": 0,
        },
    )

    assert response.status_code == 201

    # The server's drawdown figure wins over the submitted 0.
    assert Decimal(response.json()["quantity_produced"]) == (
        Decimal("3")
    )


def test_create_transaction_rejects_invalid_unit_price(client, db):
    product = create_test_product(db)

    response = client.post(
        "/api/transactions",
        json={
            "product_id": product.id,
            "transaction_date": "2026-11-02T10:00:00",
            "quantity": "5",
            "unit_price": "0",
            "unit_profit": "800.0000",
        },
    )

    assert response.status_code == 422

    db.delete(product)
    db.commit()

def test_production_cost_uses_quantity_produced_not_sold(
    client, db, two_cycles,
):
    product = create_test_product(db)

    # Applied through the ledger so the auto-filled
    # quantity_produced is 20 - the figure this test used to
    # submit. Intent unchanged: cost follows PRODUCED (20),
    # revenue follows SOLD (15).
    apply_production_to_cycle(
        db, two_cycles[0].id, product.id, 20,
    )

    # Validation Case 2: quantity_produced (20) != quantity sold (15) -
    # sales must be based on units sold, production cost on units
    # produced.
    response = client.post(
        "/api/transactions",
        json={
            "product_id": product.id,
            "transaction_date": "2026-11-02T10:00:00",
            "quantity_produced": "20",
            "quantity": "15",
            "unit_price": "3500.00",
            "production_cost": "2000.00",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert Decimal(data["total_sales"]) == Decimal("52500.00")
    assert Decimal(data["production_cost"]) == Decimal("40000.00")
    assert Decimal(data["total_profit"]) == Decimal("12500.0000")

    # Scoped purge first: this test applied production for this
    # product, and production_application_items.product_id is
    # RESTRICT, so the product cannot be deleted until its own
    # ledger rows are gone. Scoped to this product only.
    purge_ledger(db, product_ids=[product.id])

    db.delete(product)
    db.commit()


def test_zero_production_cost_per_unit(
    client, db, two_cycles,
):
    product = create_test_product(db)

    apply_production_to_cycle(
        db, two_cycles[0].id, product.id, 10,
    )

    # Validation Case 4: a per-unit production cost of 0 must not
    # reduce profit at all.
    response = client.post(
        "/api/transactions",
        json={
            "product_id": product.id,
            "transaction_date": "2026-11-02T10:00:00",
            "quantity_produced": "10",
            "quantity": "10",
            "unit_price": "3500.00",
            "production_cost": "0",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert Decimal(data["total_sales"]) == Decimal("35000.00")
    assert Decimal(data["production_cost"]) == Decimal("0.00")
    assert Decimal(data["total_profit"]) == Decimal("35000.0000")

    # Scoped purge first: this test applied production for this
    # product, and production_application_items.product_id is
    # RESTRICT, so the product cannot be deleted until its own
    # ledger rows are gone. Scoped to this product only.
    purge_ledger(db, product_ids=[product.id])

    db.delete(product)
    db.commit()


def test_calculate_transaction_values_zero_quantity_sold():
    # Validation Case 3: quantity sold = 0 (SalesTransactionCreate
    # requires quantity > 0, so this can't be submitted through the
    # live API - verified directly against the calculation function
    # instead). Production cost must still be charged against units
    # PRODUCED even when nothing sold, and unit_profit must not divide
    # by zero.
    values = calculate_transaction_values(
        Decimal("10"),
        Decimal("0"),
        Decimal("3500.00"),
        Decimal("2000.00"),
    )

    assert values["total_sales"] == Decimal("0.00")
    assert values["production_cost"] == Decimal("20000.00")
    assert values["total_profit"] == Decimal("-20000.0000")
    assert values["unit_profit"] == Decimal("0.0000")


def test_create_transaction_rejects_negative_production_cost(
    client,
    db,
):
    product = create_test_product(db)

    response = client.post(
        "/api/transactions",
        json={
            "product_id": product.id,
            "transaction_date": "2026-11-02T10:00:00",
            "quantity_produced": "6",
            "quantity": "5",
            "unit_price": "3200.00",
            "production_cost": "-1.00",
        },
    )

    assert response.status_code == 422

    db.delete(product)
    db.commit()
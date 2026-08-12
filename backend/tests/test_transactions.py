from datetime import datetime
from decimal import Decimal

from app.database.models import Product, SalesTransaction


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


def test_create_transaction(client, db):
    product = create_test_product(db)

    response = client.post(
        "/api/transactions",
        json={
            "product_id": product.id,
            "transaction_date": "2026-08-10T10:00:00",
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
    assert Decimal(data["production_cost"]) == Decimal("3000.00")
    assert Decimal(data["total_sales"]) == Decimal("16000.00")
    assert Decimal(data["unit_profit"]) == Decimal("2600.0000")
    assert Decimal(data["total_profit"]) == Decimal("13000.0000")

    db.delete(product)
    db.commit()


def test_create_transaction_product_not_found(client):
    response = client.post(
        "/api/transactions",
        json={
            "product_id": 999999,
            "transaction_date": "2026-08-10T10:00:00",
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
            "transaction_date": "2026-08-10T10:00:00",
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

    response = client.get("/api/transactions")

    assert response.status_code == 200

    data = response.json()

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


def test_update_transaction_recalculates_totals(client, db):
    product = create_test_product(db)

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
    assert Decimal(data["production_cost"]) == Decimal("5000.00")
    assert Decimal(data["total_sales"]) == Decimal("30000.00")
    assert Decimal(data["unit_profit"]) == Decimal("2500.0000")
    assert Decimal(data["total_profit"]) == Decimal("25000.0000")

    db.delete(transaction)
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
            "transaction_date": "2026-08-10T10:00:00",
            "quantity": "0",
            "unit_price": "3200.00",
            "unit_profit": "800.0000",
        },
    )

    assert response.status_code == 422

    db.delete(product)
    db.commit()

def test_create_transaction_rejects_invalid_quantity_produced(
    client,
    db,
):
    product = create_test_product(db)

    response = client.post(
        "/api/transactions",
        json={
            "product_id": product.id,
            "transaction_date": "2026-08-10T10:00:00",
            "quantity_produced": "0",
            "quantity": "5",
            "unit_price": "3200.00",
            "production_cost": "3000.00",
        },
    )

    assert response.status_code == 422

    db.delete(product)
    db.commit()


def test_create_transaction_rejects_invalid_unit_price(client, db):
    product = create_test_product(db)

    response = client.post(
        "/api/transactions",
        json={
            "product_id": product.id,
            "transaction_date": "2026-08-10T10:00:00",
            "quantity": "5",
            "unit_price": "0",
            "unit_profit": "800.0000",
        },
    )

    assert response.status_code == 422

    db.delete(product)
    db.commit()

def test_create_transaction_rejects_negative_production_cost(
    client,
    db,
):
    product = create_test_product(db)

    response = client.post(
        "/api/transactions",
        json={
            "product_id": product.id,
            "transaction_date": "2026-08-10T10:00:00",
            "quantity_produced": "6",
            "quantity": "5",
            "unit_price": "3200.00",
            "production_cost": "-1.00",
        },
    )

    assert response.status_code == 422

    db.delete(product)
    db.commit()
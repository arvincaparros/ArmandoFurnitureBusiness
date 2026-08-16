from datetime import datetime
from decimal import Decimal

from app.database.models import Product, SalesTransaction
from app.services.transaction import calculate_transaction_values


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
    # production_cost in the request is PER-UNIT (3000); the stored/
    # returned value is the TOTAL: quantity_produced (6) x 3000.
    assert Decimal(data["production_cost"]) == Decimal("18000.00")
    assert Decimal(data["total_sales"]) == Decimal("16000.00")
    assert Decimal(data["unit_profit"]) == Decimal("-400.0000")
    assert Decimal(data["total_profit"]) == Decimal("-2000.0000")

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
    # production_cost in the PATCH is PER-UNIT (5000); quantity_produced
    # is unchanged (6), so the stored/returned total is 6 x 5000.
    assert Decimal(data["production_cost"]) == Decimal("30000.00")
    assert Decimal(data["total_sales"]) == Decimal("30000.00")
    assert Decimal(data["unit_profit"]) == Decimal("0.0000")
    assert Decimal(data["total_profit"]) == Decimal("0.0000")

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

def test_production_cost_uses_quantity_produced_not_sold(client, db):
    product = create_test_product(db)

    # Validation Case 2: quantity_produced (20) != quantity sold (15) -
    # sales must be based on units sold, production cost on units
    # produced.
    response = client.post(
        "/api/transactions",
        json={
            "product_id": product.id,
            "transaction_date": "2026-08-10T10:00:00",
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

    db.delete(product)
    db.commit()


def test_zero_production_cost_per_unit(client, db):
    product = create_test_product(db)

    # Validation Case 4: a per-unit production cost of 0 must not
    # reduce profit at all.
    response = client.post(
        "/api/transactions",
        json={
            "product_id": product.id,
            "transaction_date": "2026-08-10T10:00:00",
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
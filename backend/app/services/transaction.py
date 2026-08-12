from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Product, SalesTransaction
from app.schemas.transaction import (
    SalesTransactionCreate,
    SalesTransactionUpdate,
)


def get_transactions(
    db: Session,
) -> list[SalesTransaction]:
    statement = (
        select(SalesTransaction)
        .order_by(
            SalesTransaction.transaction_date,
            SalesTransaction.id,
        )
    )

    return list(db.scalars(statement).all())


def get_transaction(
    db: Session,
    transaction_id: int,
) -> SalesTransaction | None:
    statement = select(SalesTransaction).where(
        SalesTransaction.id == transaction_id
    )

    return db.scalars(statement).first()


def calculate_transaction_values(
    quantity: Decimal,
    unit_price: Decimal,
    production_cost: Decimal,
) -> dict:
    total_sales = (
        quantity * unit_price
    ).quantize(Decimal("0.01"))

    total_profit = (
        total_sales - production_cost
    ).quantize(Decimal("0.0000"))

    unit_profit = (
        total_profit / quantity
    ).quantize(Decimal("0.0000"))

    return {
        "total_sales": total_sales,
        "unit_profit": unit_profit,
        "total_profit": total_profit,
    }

def generate_transaction_number(db: Session) -> str:
    last_id = db.scalar(
        select(func.max(SalesTransaction.id))
    )

    next_id = (last_id or 0) + 1

    return f"TRX-{next_id:06d}"

def create_transaction(
    db: Session,
    transaction_data: SalesTransactionCreate,
) -> SalesTransaction:
    product = db.get(
        Product,
        transaction_data.product_id,
    )

    if product is None:
        raise ValueError("Product not found")

    if not product.is_active:
        raise ValueError(
            "Cannot create transaction for inactive product"
        )

    values = calculate_transaction_values(
        transaction_data.quantity,
        transaction_data.unit_price,
        transaction_data.production_cost,
    )

    transaction = SalesTransaction(
        transaction_number=generate_transaction_number(db),
        product_id=transaction_data.product_id,
        transaction_date=transaction_data.transaction_date,
        quantity_produced=transaction_data.quantity_produced,
        quantity=transaction_data.quantity,
        unit_price=transaction_data.unit_price,
        total_sales=values["total_sales"],
        production_cost=transaction_data.production_cost,
        unit_profit=values["unit_profit"],
        total_profit=values["total_profit"],
    )

    try:
        db.add(transaction)
        db.commit()
        db.refresh(transaction)

        return transaction

    except Exception:
        db.rollback()
        raise


def update_transaction(
    db: Session,
    transaction: SalesTransaction,
    transaction_data: SalesTransactionUpdate,
) -> SalesTransaction:
    update_data = transaction_data.model_dump(
        exclude_unset=True
    )

    quantity = update_data.get(
        "quantity",
        transaction.quantity,
    )

    unit_price = update_data.get(
        "unit_price",
        transaction.unit_price,
    )

    production_cost = update_data.get(
        "production_cost",
        transaction.production_cost,
    )

    values = calculate_transaction_values(
        quantity,
        unit_price,
        production_cost,
    )

    for field, value in update_data.items():
        setattr(transaction, field, value)

    transaction.total_sales = values["total_sales"]
    transaction.unit_profit = values["unit_profit"]
    transaction.total_profit = values["total_profit"]

    try:
        db.commit()
        db.refresh(transaction)

        return transaction

    except Exception:
        db.rollback()
        raise


def delete_transaction(
    db: Session,
    transaction: SalesTransaction,
) -> None:
    try:
        db.delete(transaction)
        db.commit()

    except Exception:
        db.rollback()
        raise
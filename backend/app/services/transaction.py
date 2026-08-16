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
    quantity_produced: Decimal,
    quantity: Decimal,
    unit_price: Decimal,
    production_cost_per_unit: Decimal,
) -> dict:
    # unit_price/production_cost_per_unit are both per-unit inputs.
    # Sales revenue is earned on units SOLD; production cost is
    # incurred on units PRODUCED - these are deliberately different
    # quantities (see the per-unit production cost requirement).
    # production_cost here is the computed TOTAL, mirroring total_sales
    # - the SalesTransaction.production_cost column already documents
    # itself as "Total production cost associated with this
    # transaction", so this was always its intended meaning; only the
    # multiplication by quantity_produced was previously missing.
    total_sales = (
        quantity * unit_price
    ).quantize(Decimal("0.01"))

    production_cost = (
        quantity_produced * production_cost_per_unit
    ).quantize(Decimal("0.01"))

    total_profit = (
        total_sales - production_cost
    ).quantize(Decimal("0.0000"))

    unit_profit = (
        (total_profit / quantity).quantize(Decimal("0.0000"))
        if quantity != 0
        else Decimal("0.0000")
    )

    return {
        "total_sales": total_sales,
        "production_cost": production_cost,
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
        transaction_data.quantity_produced,
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
        production_cost=values["production_cost"],
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

    quantity_produced = update_data.get(
        "quantity_produced",
        transaction.quantity_produced,
    )

    quantity = update_data.get(
        "quantity",
        transaction.quantity,
    )

    unit_price = update_data.get(
        "unit_price",
        transaction.unit_price,
    )

    # transaction.production_cost is the stored TOTAL (see
    # calculate_transaction_values). If this request doesn't send a
    # new production_cost, reconstruct the per-unit rate that produced
    # the currently-stored total using the quantity_produced that was
    # in effect when it was last saved - not the raw stored total
    # itself, which would otherwise be multiplied again below and
    # silently inflate the cost.
    if "production_cost" in update_data:
        production_cost_per_unit = update_data["production_cost"]
    else:
        production_cost_per_unit = (
            transaction.production_cost
            / transaction.quantity_produced
        )

    values = calculate_transaction_values(
        quantity_produced,
        quantity,
        unit_price,
        production_cost_per_unit,
    )

    for field, value in update_data.items():
        setattr(transaction, field, value)

    transaction.total_sales = values["total_sales"]
    transaction.production_cost = values["production_cost"]
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
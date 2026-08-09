from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    Product,
    ProductionAllocation,
    ProductionCycle,
)
from app.schemas.allocation import (
    ProductionAllocationCreate,
    ProductionAllocationUpdate,
)


def get_allocations(
    db: Session,
    cycle_id: int,
) -> list[ProductionAllocation]:
    statement = (
        select(ProductionAllocation)
        .where(
            ProductionAllocation.production_cycle_id == cycle_id
        )
        .order_by(ProductionAllocation.id)
    )

    return list(
        db.scalars(statement).all()
    )


def get_allocation(
    db: Session,
    cycle_id: int,
    product_id: int,
) -> ProductionAllocation | None:
    statement = select(ProductionAllocation).where(
        ProductionAllocation.production_cycle_id == cycle_id,
        ProductionAllocation.product_id == product_id,
    )

    return db.scalars(statement).first()


def create_allocation(
    db: Session,
    cycle_id: int,
    data: ProductionAllocationCreate,
) -> ProductionAllocation:
    cycle = db.get(
        ProductionCycle,
        cycle_id,
    )

    if cycle is None:
        raise ValueError(
            "Production cycle not found"
        )

    product = db.get(
        Product,
        data.product_id,
    )

    if product is None:
        raise ValueError(
            "Product not found"
        )

    existing = get_allocation(
        db,
        cycle_id,
        data.product_id,
    )

    if existing is not None:
        raise ValueError(
            "Product already has an allocation in this production cycle"
        )

    allocation = ProductionAllocation(
        production_cycle_id=cycle_id,
        product_id=data.product_id,
        quantity=data.quantity,
    )

    try:
        db.add(allocation)
        db.commit()
        db.refresh(allocation)

        return allocation

    except Exception:
        db.rollback()
        raise


def update_allocation(
    db: Session,
    allocation: ProductionAllocation,
    data: ProductionAllocationUpdate,
) -> ProductionAllocation:
    allocation.quantity = data.quantity

    try:
        db.commit()
        db.refresh(allocation)

        return allocation

    except Exception:
        db.rollback()
        raise


def delete_allocation(
    db: Session,
    allocation: ProductionAllocation,
) -> None:
    try:
        db.delete(allocation)
        db.commit()

    except Exception:
        db.rollback()
        raise
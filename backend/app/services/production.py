from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import ProductionCycle
from app.schemas.production import (
    ProductionCycleCreate,
    ProductionCycleUpdate,
)


def get_production_cycles(
    db: Session,
) -> list[ProductionCycle]:
    statement = (
        select(ProductionCycle)
        .order_by(ProductionCycle.id)
    )

    return list(db.scalars(statement).all())


def get_production_cycle(
    db: Session,
    cycle_id: int,
) -> ProductionCycle | None:
    statement = select(ProductionCycle).where(
        ProductionCycle.id == cycle_id
    )

    return db.scalars(statement).first()


def get_latest_production_cycle(
    db: Session,
) -> ProductionCycle | None:
    """
    Canonical "latest production cycle" resolution for the whole
    system - see backend/docs/ for the audit that established this
    rule. created_at is the primary sort key (not id alone) so this
    stays correct even if cycles are ever created or backfilled out
    of id order; id DESC breaks ties. status is intentionally not
    considered here - "latest created" is not yet defined as
    "current" (that is a separate, not-yet-made decision).
    """

    statement = (
        select(ProductionCycle)
        .order_by(
            ProductionCycle.created_at.desc(),
            ProductionCycle.id.desc(),
        )
        .limit(1)
    )

    return db.scalar(statement)


def validate_cycle_dates(
    start_date,
    end_date,
) -> None:
    if end_date < start_date:
        raise ValueError(
            "end_date must be greater than or equal to start_date"
        )


def create_production_cycle(
    db: Session,
    cycle_data: ProductionCycleCreate,
) -> ProductionCycle:
    validate_cycle_dates(
        cycle_data.start_date,
        cycle_data.end_date,
    )

    cycle = ProductionCycle(
        cycle_date=cycle_data.cycle_date,
        start_date=cycle_data.start_date,
        end_date=cycle_data.end_date,
        status=cycle_data.status.value,
    )

    try:
        db.add(cycle)
        db.commit()
        db.refresh(cycle)

        return cycle

    except Exception:
        db.rollback()
        raise


def update_production_cycle(
    db: Session,
    cycle: ProductionCycle,
    cycle_data: ProductionCycleUpdate,
) -> ProductionCycle:
    update_data = cycle_data.model_dump(
        exclude_unset=True
    )

    if (
        "start_date" in update_data
        or "end_date" in update_data
    ):
        start_date = update_data.get(
            "start_date",
            cycle.start_date,
        )

        end_date = update_data.get(
            "end_date",
            cycle.end_date,
        )

        validate_cycle_dates(
            start_date,
            end_date,
        )

    if "status" in update_data:
        update_data["status"] = (
            update_data["status"].value
        )

    for field, value in update_data.items():
        setattr(cycle, field, value)

    try:
        db.commit()
        db.refresh(cycle)

        return cycle

    except Exception:
        db.rollback()
        raise


def delete_production_cycle(
    db: Session,
    cycle: ProductionCycle,
) -> None:
    try:
        db.delete(cycle)
        db.commit()

    except Exception:
        db.rollback()
        raise
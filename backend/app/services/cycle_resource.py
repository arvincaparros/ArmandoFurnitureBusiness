from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    CycleResource,
    ProductionCycle,
    Resource,
)
from app.schemas.production import (
    CycleResourceCreate,
    CycleResourceUpdate,
)


def get_cycle_resources(
    db: Session,
    cycle_id: int,
) -> list[CycleResource]:
    statement = (
        select(CycleResource)
        .where(
            CycleResource.production_cycle_id == cycle_id
        )
        .order_by(CycleResource.id)
    )

    return list(
        db.scalars(statement).all()
    )


def get_cycle_resource(
    db: Session,
    cycle_id: int,
    resource_id: int,
) -> CycleResource | None:
    statement = select(CycleResource).where(
        CycleResource.production_cycle_id == cycle_id,
        CycleResource.resource_id == resource_id,
    )

    return db.scalars(statement).first()


def create_cycle_resource(
    db: Session,
    cycle_id: int,
    data: CycleResourceCreate,
) -> CycleResource:
    cycle = db.get(
        ProductionCycle,
        cycle_id,
    )

    if cycle is None:
        raise ValueError(
            "Production cycle not found"
        )

    resource = db.get(
        Resource,
        data.resource_id,
    )

    if resource is None:
        raise ValueError(
            "Resource not found"
        )

    existing = get_cycle_resource(
        db,
        cycle_id,
        data.resource_id,
    )

    if existing is not None:
        raise ValueError(
            "Resource already exists in this production cycle"
        )

    cycle_resource = CycleResource(
        production_cycle_id=cycle_id,
        resource_id=data.resource_id,
        available_quantity=data.available_quantity,
        unit_price=data.unit_price,
    )

    try:
        db.add(cycle_resource)
        db.commit()
        db.refresh(cycle_resource)

        return cycle_resource

    except Exception:
        db.rollback()
        raise


def update_cycle_resource(
    db: Session,
    cycle_resource: CycleResource,
    data: CycleResourceUpdate,
) -> CycleResource:
    update_data = data.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(
            cycle_resource,
            field,
            value,
        )

    try:
        db.commit()
        db.refresh(cycle_resource)

        return cycle_resource

    except Exception:
        db.rollback()
        raise


def delete_cycle_resource(
    db: Session,
    cycle_resource: CycleResource,
) -> None:
    try:
        db.delete(cycle_resource)
        db.commit()

    except Exception:
        db.rollback()
        raise
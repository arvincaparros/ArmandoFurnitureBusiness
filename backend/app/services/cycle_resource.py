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


def _requires_positive_unit_price(resource: Resource) -> bool:
    # Matches resource_utilization.py's _classify_resource_type():
    # only "labor" is exempt from needing a real unit price, since
    # product labor cost is tracked separately via Product.labor_cost.
    return resource.resource_type.strip().lower() != "labor"


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

    if (
        _requires_positive_unit_price(resource)
        and data.unit_price <= 0
    ):
        raise ValueError(
            "Unit price must be greater than 0 for this resource type"
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

    # An explicit `null` for either field is accepted by
    # CycleResourceUpdate's `Decimal | None` type (only unsent fields
    # are excluded by exclude_unset, not explicit nulls) - both
    # columns are NOT NULL, so without this check a null would either
    # crash the comparison below (unit_price) or reach db.commit() and
    # raise an unhandled IntegrityError (available_quantity), neither
    # of which the router's `except ValueError` catches.
    if "unit_price" in update_data and update_data["unit_price"] is None:
        raise ValueError("unit_price cannot be null")

    if (
        "available_quantity" in update_data
        and update_data["available_quantity"] is None
    ):
        raise ValueError("available_quantity cannot be null")

    effective_unit_price = update_data.get(
        "unit_price",
        cycle_resource.unit_price,
    )

    if (
        _requires_positive_unit_price(cycle_resource.resource)
        and effective_unit_price <= 0
    ):
        raise ValueError(
            "Unit price must be greater than 0 for this resource type"
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
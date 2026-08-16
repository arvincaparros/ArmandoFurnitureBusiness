from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import Resource
from app.schemas.resource import ResourceCreate, ResourceUpdate


DUPLICATE_NAME_ERROR = "A resource with this name already exists."


def get_resources(
    db: Session,
    include_inactive: bool = False,
) -> list[Resource]:
    statement = select(Resource).order_by(Resource.id)

    if not include_inactive:
        statement = statement.where(Resource.is_active.is_(True))

    return list(db.scalars(statement).all())


def get_resource(
    db: Session,
    resource_id: int,
) -> Resource | None:
    statement = select(Resource).where(
        Resource.id == resource_id
    )

    return db.scalars(statement).first()


def create_resource(
    db: Session,
    resource_data: ResourceCreate,
) -> Resource:
    resource = Resource(
        name=resource_data.name,
        resource_type=resource_data.resource_type,
        unit=resource_data.unit,
        is_active=resource_data.is_active,
    )

    try:
        db.add(resource)
        db.commit()
        db.refresh(resource)

        return resource

    except IntegrityError as exc:
        db.rollback()
        raise ValueError(DUPLICATE_NAME_ERROR) from exc

    except Exception:
        db.rollback()
        raise


def update_resource(
    db: Session,
    resource: Resource,
    resource_data: ResourceUpdate,
) -> Resource:
    update_data = resource_data.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(resource, field, value)

    try:
        db.commit()
        db.refresh(resource)

        return resource

    except IntegrityError as exc:
        db.rollback()
        raise ValueError(DUPLICATE_NAME_ERROR) from exc

    except Exception:
        db.rollback()
        raise


def delete_resource(
    db: Session,
    resource: Resource,
) -> None:
    try:
        resource.is_active = False

        db.commit()

    except Exception:
        db.rollback()
        raise
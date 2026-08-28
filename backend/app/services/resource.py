from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import Resource
from app.schemas.resource import ResourceCreate, ResourceUpdate


DUPLICATE_NAME_ERROR = "A resource with this name already exists."


def _find_by_normalized_name(
    db: Session,
    name: str,
    exclude_id: int | None = None,
) -> Resource | None:
    """
    Case/whitespace-insensitive name lookup across ALL resources
    (active and inactive) - the plain `UniqueConstraint("name")` on
    the table only rejects an exact-case duplicate at the DB layer,
    so callers that need to treat "Circular Saw" and "circular saw "
    as the same resource (duplicate blocking, delete+re-add matching)
    go through this instead of a raw Resource.name == name lookup.
    """
    statement = select(Resource).where(
        func.lower(func.trim(Resource.name)) == name.strip().lower()
    )

    if exclude_id is not None:
        statement = statement.where(Resource.id != exclude_id)

    return db.scalars(statement).first()


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
    name = resource_data.name.strip()

    existing = _find_by_normalized_name(db, name)

    if existing is not None:
        if existing.is_active:
            raise ValueError(DUPLICATE_NAME_ERROR)

        # A resource by this name was soft-deleted earlier (see
        # delete_resource - is_active is set to False, the row is
        # never removed). Reactivate that same row instead of
        # inserting a new one, so its id stays intact and any
        # ProductResourceRequirement/CycleResource rows that already
        # reference it keep pointing at a live resource rather than
        # being orphaned onto a duplicate row.
        existing.name = name
        existing.resource_type = resource_data.resource_type
        existing.unit = resource_data.unit
        existing.is_active = True

        try:
            db.commit()
            db.refresh(existing)

            return existing

        except IntegrityError as exc:
            db.rollback()
            raise ValueError(DUPLICATE_NAME_ERROR) from exc

        except Exception:
            db.rollback()
            raise

    resource = Resource(
        name=name,
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

    if update_data.get("name") is not None:
        update_data["name"] = update_data["name"].strip()

        conflicting = _find_by_normalized_name(
            db,
            update_data["name"],
            exclude_id=resource.id,
        )

        if conflicting is not None:
            raise ValueError(DUPLICATE_NAME_ERROR)

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
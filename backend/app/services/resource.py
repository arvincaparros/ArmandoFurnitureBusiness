from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import Resource
from app.schemas.resource import ResourceCreate, ResourceUpdate


DUPLICATE_NAME_ERROR = "A resource with this name already exists."
DUPLICATE_INACTIVE_NAME_ERROR = (
    "A resource with this name already exists and is inactive."
)


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
    as the same resource (create/update duplicate blocking) go
    through this instead of a raw Resource.name == name lookup.
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
    """
    A name matching an existing resource is always rejected, whether
    that resource is active or soft-deleted (see delete_resource):
    the row is kept - not removed - so its id and every historical
    reference to it stay intact, and a create must never revive it
    implicitly. Re-adding a deleted resource's name therefore returns
    DUPLICATE_INACTIVE_NAME_ERROR instead of reactivating the old row.

    The `_find_by_normalized_name` lookup below is a SELECT-then-act
    check, not an atomic guarantee - two concurrent requests for
    case/whitespace-variant names (e.g. "Circular Saw" and
    "Circular saw") can both run it before either has committed, both
    see no match, and both insert successfully, since the table's
    plain `UniqueConstraint("name")` is exact-string and never catches
    that. This is believed to be exactly how production ended up with
    a split Circular Saw identity (see migration 78b1304118b7's
    docstring). The real, final backstop against that race is the
    `ix_resources_normalized_name` unique index on
    `lower(trim(name))` added by that same migration: whichever of two
    racing commits loses hits a real IntegrityError on that index, and
    every commit() below is already wrapped to turn ANY IntegrityError
    - this one included, not just the pre-existing exact-name
    constraint - into the same DUPLICATE_NAME_ERROR the non-race path
    already returns as a clean 409, never a raw 500.
    """

    name = resource_data.name.strip()

    existing = _find_by_normalized_name(db, name)

    if existing is not None:
        if existing.is_active:
            raise ValueError(DUPLICATE_NAME_ERROR)

        # A resource by this name was soft-deleted earlier (see
        # delete_resource - is_active is set to False, the row is
        # never removed). Creating it again would either silently
        # reactivate it or insert a second row under the same name -
        # neither is allowed, so the caller is told exactly what it
        # collided with.
        raise ValueError(DUPLICATE_INACTIVE_NAME_ERROR)

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
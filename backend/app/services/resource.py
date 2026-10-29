from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import (
    CycleResource,
    Product,
    ProductionCycle,
    ProductResourceRequirement,
    Resource,
)
from app.schemas.resource import ResourceCreate, ResourceUpdate


DUPLICATE_NAME_ERROR = "A resource with this name already exists."
DUPLICATE_INACTIVE_NAME_ERROR = (
    "A resource with this name already exists and is inactive."
)

# Permanent delete is only ever offered for an already-soft-deleted
# row (see delete_resource). Refusing an active resource keeps the two
# delete endpoints from overlapping: DELETE /{id} deactivates, and
# DELETE /{id}/permanent removes - it never deactivates as a
# convenience first, since that would turn one irreversible click into
# two state changes the caller didn't ask for.
PERMANENT_DELETE_ACTIVE_ERROR = (
    "This resource is still active and cannot be deleted "
    "permanently. Deactivate it first, then delete it."
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


def find_resource_references(
    db: Session,
    resource: Resource,
) -> dict[str, list[str]]:
    """
    The rows that must BLOCK a permanent delete rather than be taken
    down with it.

    Both of these FKs are ON DELETE CASCADE in the database
    (`product_resource_requirements.resource_id` and
    `cycle_resources.resource_id`), so a bare `db.delete(resource)`
    would silently destroy them - product BOM lines and a cycle's
    availability/price - with no error and no audit trail. The
    optimizer would then solve against incomplete recipes and still
    return a plausible-looking plan. So the guard lives here, in the
    application, and the cascade is never relied on as the deletion
    mechanism.

    `resource_utilization_history_items` is deliberately NOT checked:
    its FK is ON DELETE SET NULL and every field a history view
    renders (resource_name/resource_type/unit plus the calculated
    quantities) is snapshotted onto the row at creation time, so that
    history stays complete and fully displayable after the Resource
    it pointed at is gone. See the ResourceUtilizationHistoryItem
    docstring in app/database/models.py.

    Returns display-ready labels, not ids, so the 409 can name
    exactly what the caller has to clear first.
    """

    product_names = list(
        db.scalars(
            select(Product.name)
            .join(
                ProductResourceRequirement,
                ProductResourceRequirement.product_id == Product.id,
            )
            .where(
                ProductResourceRequirement.resource_id == resource.id
            )
            .order_by(Product.name)
        ).all()
    )

    cycle_labels = [
        f"#{cycle_id} ({cycle_date:%Y-%m-%d})"
        for cycle_id, cycle_date in db.execute(
            select(
                ProductionCycle.id,
                ProductionCycle.cycle_date,
            )
            .join(
                CycleResource,
                CycleResource.production_cycle_id
                == ProductionCycle.id,
            )
            .where(CycleResource.resource_id == resource.id)
            .order_by(ProductionCycle.id)
        ).all()
    ]

    return {
        "products": product_names,
        "production_cycles": cycle_labels,
    }


def format_resource_reference_message(
    resource: Resource,
    references: dict[str, list[str]],
) -> str:
    blockers = []

    if references["products"]:
        blockers.append(
            "resource requirements on "
            + ", ".join(references["products"])
        )

    if references["production_cycles"]:
        blockers.append(
            "availability and pricing in production cycle "
            + ", ".join(references["production_cycles"])
        )

    return (
        f"'{resource.name}' cannot be deleted permanently because it "
        "is still used by " + "; and ".join(blockers) + ". Remove "
        "those first - this endpoint never deletes them for you. "
        "Resource utilization history is always kept and never "
        "blocks deletion."
    )


def permanently_delete_resource(
    db: Session,
    resource: Resource,
) -> None:
    """
    Removes the catalogue row outright - the one path in this module
    that is NOT reversible. Both guards run before any write, so a
    rejected call leaves the database byte-identical.

    Succeeding here frees the resource's name: `create_resource`
    blocks a name held by ANY existing row, active or soft-deleted
    (DUPLICATE_INACTIVE_NAME_ERROR), and that reservation only exists
    because the soft-deleted row itself does. Once the row is gone
    there is nothing left to collide with, so the name becomes
    available again - that is the intended difference from a soft
    delete, not a regression of the reservation rule.
    """

    if resource.is_active:
        raise ValueError(PERMANENT_DELETE_ACTIVE_ERROR)

    references = find_resource_references(db, resource)

    if references["products"] or references["production_cycles"]:
        raise ValueError(
            format_resource_reference_message(resource, references)
        )

    try:
        db.delete(resource)
        db.commit()

    except Exception:
        db.rollback()
        raise
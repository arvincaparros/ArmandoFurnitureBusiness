from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database.models import (
    CycleResource,
    ProductionApplication,
    ProductionApplicationItem,
    ProductionApplicationResourceItem,
)


def generate_application_number(db: Session) -> str:
    """
    "PA-0001", "PA-0002", ... - same sequential friendly-id convention
    as transaction.py::generate_transaction_number and
    resource_utilization_history.py::generate_utilization_number.
    """

    last_id = db.scalar(
        select(func.max(ProductionApplication.id))
    )

    return f"PA-{(last_id or 0) + 1:04d}"


def has_application_for_run(
    db: Session,
    optimization_run_id: int,
) -> bool:
    """
    Pre-flight duplicate check so the caller can return a clean,
    explanatory 400 instead of surfacing the
    uq_production_application_run IntegrityError. The constraint - not
    this - is the real guarantee; this only makes the common case
    readable.
    """

    return (
        db.scalar(
            select(func.count(ProductionApplication.id)).where(
                ProductionApplication.optimization_run_id
                == optimization_run_id
            )
        )
        or 0
    ) > 0


def save_production_application(
    db: Session,
    cycle_id: int,
    optimization_run_id: int,
    produced_by_product_id: dict[int, Decimal],
    consumed_resources: list[dict],
) -> ProductionApplication:
    """
    Appends one apply event plus its product and resource items.

    Deliberately does NOT commit - the caller
    (optimization.py::apply_optimization) commits this together with
    the ProductionAllocation rows and the resource utilization
    snapshot in one transaction, so production history, the current
    plan, and the utilization snapshot can never disagree about
    whether an apply happened. Same contract as
    resource_utilization_history.py::save_resource_utilization_history.

    Non-positive produced quantities are skipped rather than stored:
    they would add rows that change no derived figure, and
    apply_optimization already skips them for ProductionAllocation.
    """

    application = ProductionApplication(
        application_number=generate_application_number(db),
        production_cycle_id=cycle_id,
        optimization_run_id=optimization_run_id,
        applied_at=datetime.utcnow(),
    )

    db.add(application)
    db.flush()

    db.add_all(
        [
            ProductionApplicationItem(
                production_application_id=application.id,
                product_id=product_id,
                quantity_produced=quantity,
            )
            for product_id, quantity in (
                produced_by_product_id.items()
            )
            if quantity > 0
        ]
    )

    db.add_all(
        [
            ProductionApplicationResourceItem(
                production_application_id=application.id,
                resource_id=resource["resource_id"],
                resource_name=resource["resource_name"],
                unit=resource["unit"],
                consumed_quantity=resource["consumed_quantity"],
            )
            for resource in consumed_resources
            if resource["consumed_quantity"] > 0
        ]
    )

    db.flush()

    return application


def get_cycle_consumed_by_resource(
    db: Session,
    cycle_id: int,
) -> dict[int, Decimal]:
    """
    resource_id -> total raw material already consumed by every
    application in this cycle. Subtracted from
    CycleResource.available_quantity to get the capacity a NEW
    application may spend, which is what makes consumption
    incremental: an application can never re-use capacity an earlier
    one in the same cycle already used.

    Rows whose resource was later deleted (resource_id NULL, ON DELETE
    SET NULL) are excluded - there is no live CycleResource row to
    offset against, and inventing a key for them would corrupt the
    lookup.
    """

    rows = db.execute(
        select(
            ProductionApplicationResourceItem.resource_id,
            func.sum(
                ProductionApplicationResourceItem.consumed_quantity
            ),
        )
        .join(
            ProductionApplication,
            ProductionApplication.id
            == (
                ProductionApplicationResourceItem
                .production_application_id
            ),
        )
        .where(
            ProductionApplication.production_cycle_id == cycle_id,
            ProductionApplicationResourceItem.resource_id.isnot(
                None
            ),
        )
        .group_by(ProductionApplicationResourceItem.resource_id)
    ).all()

    return {
        resource_id: total
        for resource_id, total in rows
        if total is not None
    }


def get_cycle_consumed_by_resource_since_update(
    db: Session,
    cycle_id: int,
) -> dict[int, Decimal]:
    """
    Like get_cycle_consumed_by_resource above, but scoped PER-RESOURCE
    to applications applied at or after that resource's own
    CycleResource.updated_at - i.e. only consumption recorded under
    the resource's CURRENT quantity ("this production week"), never
    consumption accumulated under a since-superseded one. A resource
    never edited since cycle creation (updated_at == created_at) falls
    back to the cycle's full lifetime, identical to
    get_cycle_consumed_by_resource's own result - so a cycle that has
    never had a resource quantity edited mid-stream sees no change in
    behavior at all.

    Additive and separate on purpose: get_cycle_consumed_by_resource
    itself, and every one of its other callers (apply_optimization's
    exhausted-resources explanatory message in particular), keep their
    existing all-time semantics completely unchanged. Only the
    Resource Utilization API's two GET handlers call this function.

    Never deletes or mutates a ProductionApplication/…Item/
    …ResourceItem row - a superseded week's applications are excluded
    from THIS SUM only, never from the database. Historical production
    application records remain fully intact and queryable through
    get_cycle_consumed_by_resource or direct inspection regardless of
    how many times a resource's quantity has since been edited.

    KNOWN LIMITATION (schema can't currently distinguish the two):
    CycleResource.updated_at is a single column bumped by SQLAlchemy's
    onupdate on ANY edit to that row - available_quantity OR
    unit_price, whichever was actually sent in the PATCH payload (see
    update_cycle_resource's `for field, value in update_data.items():
    setattr(...)` loop, and the model's own column comment). There is
    no separate "quantity last changed" vs "price last changed"
    timestamp without adding a new column, which is out of scope here
    (no migration was requested or made). A price-only edit will
    therefore ALSO reset this function's cutoff for that resource,
    exactly as a quantity edit would, even though no quantity actually
    changed. This is a real, reported limitation of the current data
    model, not a silent side effect introduced by this function - see
    test_resource_utilization.py::
    test_since_update_scoping_also_resets_on_a_price_only_edit for a
    test that documents it explicitly, and raise it with product/
    business if that specific case needs to behave differently (it
    would require a new "quantity_updated_at" column).
    """

    cutoff_by_resource_id = {
        cycle_resource.resource_id: cycle_resource.updated_at
        for cycle_resource in db.scalars(
            select(CycleResource).where(
                CycleResource.production_cycle_id == cycle_id
            )
        ).all()
    }

    rows = db.execute(
        select(
            ProductionApplicationResourceItem.resource_id,
            ProductionApplicationResourceItem.consumed_quantity,
            ProductionApplication.applied_at,
        )
        .join(
            ProductionApplication,
            ProductionApplication.id
            == (
                ProductionApplicationResourceItem
                .production_application_id
            ),
        )
        .where(
            ProductionApplication.production_cycle_id == cycle_id,
            ProductionApplicationResourceItem.resource_id.isnot(
                None
            ),
        )
    ).all()

    totals: dict[int, Decimal] = {}

    for resource_id, consumed_quantity, applied_at in rows:
        cutoff = cutoff_by_resource_id.get(resource_id)

        if (
            cutoff is not None
            and applied_at is not None
            and applied_at < cutoff
        ):
            continue

        totals[resource_id] = (
            totals.get(resource_id, Decimal("0"))
            + consumed_quantity
        )

    return totals


def get_latest_application_consumed_by_resource(
    db: Session,
    cycle_id: int,
) -> dict[int, Decimal]:
    """
    resource_id -> consumed_quantity recorded by ONLY the single most
    recently applied ProductionApplication for this cycle - never
    summed with any earlier application, even one applied the same
    day. This is the Resource Utilization Report's consumption source
    (see resource_utilization.py's two GET handlers): Generate
    Allocation #1 -> Apply -> the report shows #1's consumption;
    Generate Allocation #2 -> Apply -> the report REPLACES it with
    #2's consumption alone, never #1 + #2.

    Ordered by (applied_at DESC, id DESC) - the same reliable
    tiebreak get_applications() already uses elsewhere in this file.
    id is a strictly monotonic auto-increment primary key, so two
    applications that land on an identical applied_at timestamp
    (repeated Generate/Apply within the same day, even the same
    second) still resolve to exactly one unambiguous "latest" row.

    Returns {} when this cycle has no ProductionApplication at all -
    the caller distinguishes that ("no ledger to scope, fall back to
    the pre-ledger allocation-derived report") from "a latest
    application exists but recorded zero consumption" via
    get_cycle_consumed_by_resource's own non-empty check, exactly as
    the previous get_cycle_consumed_by_resource_since_update-based
    design did.

    Every row in production_applications already represents a
    SUCCESSFUL apply by construction: apply_optimization() raises and
    rolls back before writing anything on any failure (duplicate run,
    non-OPTIMAL status, no results, etc. - see its own guards above
    save_production_application's call site), so there is no "failed
    application" row for this function to additionally filter out -
    the latest row here is always the latest SUCCESSFUL one.

    Never deletes or mutates any ProductionApplication/…Item/
    …ResourceItem row - every earlier application stays fully intact
    and queryable via get_cycle_consumed_by_resource or
    get_applications regardless of how many times Apply has run
    since; only THIS report's consumption figure is scoped to the
    latest one.
    """

    latest_application_id = db.scalar(
        select(ProductionApplication.id)
        .where(
            ProductionApplication.production_cycle_id == cycle_id
        )
        .order_by(
            ProductionApplication.applied_at.desc(),
            ProductionApplication.id.desc(),
        )
        .limit(1)
    )

    if latest_application_id is None:
        return {}

    rows = db.execute(
        select(
            ProductionApplicationResourceItem.resource_id,
            func.sum(
                ProductionApplicationResourceItem.consumed_quantity
            ),
        )
        .where(
            ProductionApplicationResourceItem
            .production_application_id == latest_application_id,
            ProductionApplicationResourceItem.resource_id.isnot(
                None
            ),
        )
        .group_by(ProductionApplicationResourceItem.resource_id)
    ).all()

    return {
        resource_id: total
        for resource_id, total in rows
        if total is not None
    }


def get_cycle_produced_by_product(
    db: Session,
    cycle_id: int,
) -> dict[int, Decimal]:
    """
    product_id -> units produced by every application in THIS cycle.
    Resets naturally for a new cycle (no rows yet) while
    get_total_produced_by_product below keeps growing - that pairing
    is exactly how unsold stock survives a cycle boundary.
    """

    rows = db.execute(
        select(
            ProductionApplicationItem.product_id,
            func.sum(ProductionApplicationItem.quantity_produced),
        )
        .join(
            ProductionApplication,
            ProductionApplication.id
            == ProductionApplicationItem.production_application_id,
        )
        .where(
            ProductionApplication.production_cycle_id == cycle_id
        )
        .group_by(ProductionApplicationItem.product_id)
    ).all()

    return {
        product_id: total
        for product_id, total in rows
        if total is not None
    }


def get_total_produced_by_product(
    db: Session,
    since: datetime | None = None,
) -> dict[int, Decimal]:
    """
    product_id -> units produced across EVERY cycle, ever. The
    production half of available stock - deliberately never
    cycle-filtered, because stock that was produced and not sold is
    still stock after the cycle closes.

    `since`, when given, excludes any application whose `applied_at`
    is strictly before that instant - the ledger's effective date
    (see inventory.py::get_available_stock). An application applied
    at or after `since` is still included in full, and multiple
    qualifying applications still accumulate normally. `None` (the
    default) keeps the true all-time total.
    """

    statement = select(
        ProductionApplicationItem.product_id,
        func.sum(ProductionApplicationItem.quantity_produced),
    )

    if since is not None:
        statement = statement.join(
            ProductionApplication,
            ProductionApplication.id
            == ProductionApplicationItem.production_application_id,
        ).where(ProductionApplication.applied_at >= since)

    rows = db.execute(
        statement.group_by(ProductionApplicationItem.product_id)
    ).all()

    return {
        product_id: total
        for product_id, total in rows
        if total is not None
    }


def get_applications(
    db: Session,
    cycle_id: int | None = None,
) -> list[ProductionApplication]:
    statement = (
        select(ProductionApplication)
        .options(
            selectinload(ProductionApplication.product_items),
            selectinload(ProductionApplication.resource_items),
        )
        .order_by(
            ProductionApplication.applied_at.desc(),
            ProductionApplication.id.desc(),
        )
    )

    if cycle_id is not None:
        statement = statement.where(
            ProductionApplication.production_cycle_id == cycle_id
        )

    return list(db.scalars(statement).all())

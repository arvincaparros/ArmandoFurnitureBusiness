from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database.models import (
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

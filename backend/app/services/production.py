from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import ProductionApplication, ProductionCycle
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


def find_cycle_production_applications(
    db: Session,
    cycle: ProductionCycle,
) -> list[str]:
    """
    The production applications (by application_number) that must
    BLOCK this cycle's deletion.

    `production_applications.production_cycle_id` is ON DELETE
    RESTRICT, not CASCADE - unlike the resources.py guard, where the
    hazard was a CASCADE silently destroying rows with no error, this
    FK already refuses the delete at the database level. But a bare
    `db.delete(cycle); db.commit()` against a restricted row raises an
    uncaught IntegrityError, which would surface as a raw 500 rather
    than the clean 4xx this codebase requires for every rejection
    path. So this check runs first, in the application layer, purely
    to turn that into an actionable 409 that names the applications
    first - the ledger itself is never consulted to decide WHETHER to
    delete, only to explain why the answer is no.

    Returns display-ready application numbers, not ids, so the 409 can
    name exactly what exists in this cycle. There is no "remove them
    first and retry" here, unlike permanently_delete_resource: the
    ledger is append-only by design (see ProductionApplication's
    docstring) and has no delete path at all, so a cycle with any
    application history can never be deleted, full stop.
    """

    return list(
        db.scalars(
            select(ProductionApplication.application_number)
            .where(
                ProductionApplication.production_cycle_id == cycle.id
            )
            .order_by(ProductionApplication.id)
        ).all()
    )


def format_cycle_application_reference_message(
    cycle: ProductionCycle,
    application_numbers: list[str],
) -> str:
    return (
        f"Production cycle #{cycle.id} cannot be deleted because "
        "production has been applied to it: "
        + ", ".join(application_numbers)
        + ". Production application history is append-only and can "
        "never be deleted, so a cycle it references can never be "
        "deleted either."
    )


def delete_production_cycle(
    db: Session,
    cycle: ProductionCycle,
) -> None:
    """
    Deletes a cycle with no production history exactly as before. A
    cycle that production has been applied to is refused with a
    ValueError before any write is attempted, so a rejected call
    leaves the database byte-identical - see
    find_cycle_production_applications for why that check exists even
    though the FK is already RESTRICT.
    """

    application_numbers = find_cycle_production_applications(
        db,
        cycle,
    )

    if application_numbers:
        raise ValueError(
            format_cycle_application_reference_message(
                cycle,
                application_numbers,
            )
        )

    try:
        db.delete(cycle)
        db.commit()

    except Exception:
        db.rollback()
        raise
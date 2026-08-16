from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import (
    ResourceUtilizationHistoryItem,
    ResourceUtilizationRun,
)


def generate_utilization_number(db: Session) -> str:
    """
    Same sequential-friendly-id convention as
    app/services/transaction.py::generate_transaction_number -
    "UT-0001", "UT-0002", ... rather than the model's random-hex
    fallback default.
    """

    last_id = db.scalar(
        select(func.max(ResourceUtilizationRun.id))
    )

    next_id = (last_id or 0) + 1

    return f"UT-{next_id:04d}"


def save_resource_utilization_history(
    db: Session,
    cycle_id: int,
    utilization: dict,
) -> ResourceUtilizationRun:
    """
    Persists an immutable snapshot of an already-computed utilization
    result (see resource_utilization.py::calculate_resource_
    utilization) - one ResourceUtilizationRun plus one
    ResourceUtilizationHistoryItem per resource. Deliberately does
    NOT commit - the caller (app/services/optimization.py::
    apply_optimization) commits this together with the
    ProductionAllocation rows it just wrote, in the same transaction,
    so applying production and snapshotting its utilization succeed
    or fail together atomically.
    """

    utilization_run = ResourceUtilizationRun(
        utilization_number=generate_utilization_number(db),
        production_cycle_id=cycle_id,
    )

    db.add(utilization_run)
    db.flush()

    items = [
        ResourceUtilizationHistoryItem(
            utilization_run_id=utilization_run.id,
            resource_id=resource["resource_id"],
            resource_name=resource["resource_name"],
            resource_type=resource["resource_type"],
            unit=resource["unit"],
            available_quantity=resource["available_quantity"],
            consumed_quantity=resource["consumed_quantity"],
            remaining_quantity=resource["remaining_quantity"],
            utilization_rate=resource["utilization_rate"],
            status=resource["status"],
        )
        for resource in utilization["resources"]
    ]

    db.add_all(items)
    db.flush()

    return utilization_run


def get_resource_utilization_history(
    db: Session,
    cycle_id: int | None = None,
) -> list[ResourceUtilizationRun]:
    statement = select(ResourceUtilizationRun).order_by(
        ResourceUtilizationRun.generated_at.desc(),
        ResourceUtilizationRun.id.desc(),
    )

    if cycle_id is not None:
        statement = statement.where(
            ResourceUtilizationRun.production_cycle_id == cycle_id
        )

    return list(db.scalars(statement).all())


def get_resource_utilization_history_run(
    db: Session,
    run_id: int,
) -> ResourceUtilizationRun | None:
    return db.get(ResourceUtilizationRun, run_id)


def summarize_utilization_run(run: ResourceUtilizationRun) -> dict:
    """
    Lightweight counts for the list view (GET .../history) - full
    per-resource detail is only returned by the single-run endpoint
    (GET .../history/{id}), matching the "summary table, expand for
    detail" UX rather than repeating the same id/date across N rows.
    """

    bottleneck_count = sum(
        1 for item in run.items if item.status == "bottleneck"
    )

    at_risk_count = sum(
        1 for item in run.items if item.status == "at_risk"
    )

    return {
        "id": run.id,
        "utilization_number": run.utilization_number,
        "production_cycle_id": run.production_cycle_id,
        "generated_at": run.generated_at,
        "resource_count": len(run.items),
        "bottleneck_count": bottleneck_count,
        "at_risk_count": at_risk_count,
    }

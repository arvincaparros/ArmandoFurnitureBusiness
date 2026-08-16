from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.models import (
    OptimizationResult,
    OptimizationRun,
)


def save_optimization_history(
    db: Session,
    cycle_id: int,
    started_at: datetime,
    completed_at: datetime,
    result: dict,
) -> OptimizationRun:
    """
    Save one optimization execution and its recommended
    production quantities.
    """

    duration_ms = int(
        (
            completed_at - started_at
        ).total_seconds()
        * 1000
    )

    optimization_run = OptimizationRun(
        production_cycle_id=cycle_id,
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=duration_ms,
        status=result["status"].upper(),
        objective_value=result["objective_value"],
        total_profit=sum(
            allocation["total_profit"]
            for allocation in result["allocations"]
        ),
    )

    db.add(optimization_run)
    db.flush()
    
    optimization_results = [
        OptimizationResult(
            optimization_run_id=optimization_run.id,
            product_id=allocation["product_id"],
            recommended_quantity=allocation["quantity"],
            unit_profit=allocation["unit_profit"],
            total_profit=allocation["total_profit"],
        )
        for allocation in result["allocations"]
    ]

    db.add_all(optimization_results)

    db.commit()
    db.refresh(optimization_run)

    return optimization_run

def get_optimization_history(
    db: Session,
    cycle_id: int | None = None,
):
    statement = (
        select(OptimizationRun)
        .order_by(
            OptimizationRun.started_at.desc()
        )
    )

    if cycle_id is not None:
        statement = statement.where(
            OptimizationRun.production_cycle_id
            == cycle_id
        )

    return db.scalars(statement).all()

def get_optimization_history_run(
    db: Session,
    run_id: int,
):
    statement = (
        select(OptimizationRun)
        .where(
            OptimizationRun.id == run_id
        )
    )

    return db.scalar(statement)

def get_latest_optimization_history_run(
    db: Session,
    cycle_id: int,
) -> OptimizationRun | None:
    statement = (
        select(OptimizationRun)
        .where(
            OptimizationRun.production_cycle_id
            == cycle_id
        )
        .order_by(
            OptimizationRun.started_at.desc(),
            OptimizationRun.id.desc(),
        )
        .limit(1)
    )

    return db.scalar(statement)


def get_latest_optimal_run(
    db: Session,
    cycle_id: int,
) -> OptimizationRun | None:
    """
    Latest OPTIMAL run for one cycle - the same "newest OPTIMAL run"
    selection the frontend performs over
    /api/optimization/history?cycle_id=... (findLatestOptimalRun),
    reused here so the dashboard summary's latest_optimization_profit
    always refers to the same run as the dashboard's Expected Revenue,
    never a different cycle's or a non-OPTIMAL run.
    """

    statement = (
        select(OptimizationRun)
        .where(
            OptimizationRun.production_cycle_id
            == cycle_id,
            OptimizationRun.status == "OPTIMAL",
        )
        .order_by(
            OptimizationRun.started_at.desc(),
            OptimizationRun.id.desc(),
        )
        .limit(1)
    )

    return db.scalar(statement)
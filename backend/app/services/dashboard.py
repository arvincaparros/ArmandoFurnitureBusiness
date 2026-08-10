from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import (
    OptimizationRun,
    Product,
    ProductionAllocation,
    ProductionCycle,
    Resource,
)


def get_dashboard_summary(db: Session) -> dict:
    total_products = db.scalar(
        select(func.count(Product.id)).where(
            Product.is_active.is_(True)
        )
    ) or 0

    total_resources = db.scalar(
        select(func.count(Resource.id)).where(
            Resource.is_active.is_(True)
        )
    ) or 0

    total_production_cycles = db.scalar(
        select(func.count(ProductionCycle.id))
    ) or 0

    total_allocations = db.scalar(
        select(func.count(ProductionAllocation.id))
    ) or 0

    total_optimization_runs = db.scalar(
        select(func.count(OptimizationRun.id))
    ) or 0

    latest_optimization_profit = db.scalar(
        select(OptimizationRun.total_profit)
        .where(
            OptimizationRun.status == "OPTIMAL"
        )
        .order_by(
            OptimizationRun.started_at.desc(),
            OptimizationRun.id.desc(),
        )
        .limit(1)
    )

    return {
        "total_products": total_products,
        "total_resources": total_resources,
        "total_production_cycles": total_production_cycles,
        "total_allocations": total_allocations,
        "total_optimization_runs": total_optimization_runs,
        "latest_optimization_profit": (
            latest_optimization_profit
        ),
    }
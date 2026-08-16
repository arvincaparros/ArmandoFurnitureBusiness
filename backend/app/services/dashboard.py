from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import (
    OptimizationRun,
    Product,
    ProductionAllocation,
    ProductionCycle,
    Resource,
    SalesTransaction,
    ForecastRun,
)
from app.services.optimization_history import get_latest_optimal_run
from app.services.production import get_latest_production_cycle

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

    total_sales = db.scalar(
        select(
            func.coalesce(
                func.sum(SalesTransaction.total_sales),
                0,
            )
        )
    ) or 0

    total_sales_profit = db.scalar(
        select(
            func.coalesce(
                func.sum(SalesTransaction.total_profit),
                0,
            )
        )
    ) or 0

    # Scoped to the canonical latest production cycle (same
    # created_at DESC, id DESC rule as GET /api/production-cycles/latest)
    # so this can never surface a different cycle's profit than what
    # Expected Revenue is showing on the dashboard - see the Dashboard
    # Expected Profit Cycle-Scoping report. No fallback to an older
    # cycle's run: no OPTIMAL run in the latest cycle means None, same
    # contract as before.
    latest_cycle = get_latest_production_cycle(db)

    latest_optimization_profit = None

    if latest_cycle is not None:
        latest_optimal_run = get_latest_optimal_run(
            db, latest_cycle.id
        )

        if latest_optimal_run is not None:
            latest_optimization_profit = (
                latest_optimal_run.total_profit
            )

    latest_forecast = db.scalar(
        select(ForecastRun)
        .order_by(
            ForecastRun.created_at.desc(),
            ForecastRun.id.desc(),
        )
        .limit(1)
    )

    latest_forecast_total_quantity = None

    if latest_forecast is not None:
        latest_forecast_total_quantity = sum(
            result.forecast_quantity
            for result in latest_forecast.results
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
        "total_sales": total_sales,
        "total_sales_profit": total_sales_profit,
        "latest_forecast_period": (
            latest_forecast.forecast_period
            if latest_forecast
            else None
        ),
        "latest_forecast_created_at": (
            latest_forecast.created_at
            if latest_forecast
            else None
        ),
        "latest_forecast_total_quantity": (
            latest_forecast_total_quantity
        ),
    }
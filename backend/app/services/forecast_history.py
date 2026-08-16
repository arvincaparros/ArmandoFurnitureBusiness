from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    ForecastResult,
    ForecastRun,
)


def save_forecast_history(
    db: Session,
    forecast: dict,
) -> ForecastRun:
    """
    Save one forecast execution and its product forecasts.
    """

    forecast_run = ForecastRun(
        forecast_period=forecast["forecast_period"],
    )

    db.add(forecast_run)
    db.flush()

    forecast_results = [
        ForecastResult(
            forecast_run_id=forecast_run.id,
            product_id=product["product_id"],
            historical_quantity=product[
                "historical_quantity"
            ],
            forecast_quantity=product[
                "forecast_quantity"
            ],
            trend=product["trend"],
            confidence_level=product.get(
                "confidence_level"
            ),
            forecast_status=product.get(
                "forecast_status"
            ),
        )
        for product in forecast["products"]
    ]

    db.add_all(forecast_results)

    db.commit()
    db.refresh(forecast_run)

    return forecast_run


def get_forecast_history(
    db: Session,
) -> list[ForecastRun]:
    statement = (
        select(ForecastRun)
        .order_by(
            ForecastRun.created_at.desc(),
            ForecastRun.id.desc(),
        )
    )

    return list(db.scalars(statement).all())


def get_forecast_history_run(
    db: Session,
    run_id: int,
) -> ForecastRun | None:
    statement = (
        select(ForecastRun)
        .where(
            ForecastRun.id == run_id
        )
    )

    return db.scalar(statement)


def get_latest_forecast_history_run(
    db: Session,
) -> ForecastRun | None:
    statement = (
        select(ForecastRun)
        .order_by(
            ForecastRun.created_at.desc(),
            ForecastRun.id.desc(),
        )
        .limit(1)
    )

    return db.scalar(statement)

def build_forecast_history_response(
    run: ForecastRun,
) -> dict:
    return {
        "id": run.id,
        "forecast_period": run.forecast_period,
        "created_at": run.created_at,
        "products": [
            {
                "product_id": result.product_id,
                "historical_quantity": result.historical_quantity,
                "forecast_quantity": result.forecast_quantity,
                "trend": result.trend,
                "confidence_level": result.confidence_level,
                "forecast_status": result.forecast_status,
            }
            for result in run.results
        ],
    }

def build_forecast_history_responses(
    runs: list[ForecastRun],
) -> list[dict]:
    return [
        build_forecast_history_response(run)
        for run in runs
    ]
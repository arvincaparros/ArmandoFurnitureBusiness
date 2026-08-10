from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db

from app.schemas.forecast import (
    ForecastHistoryRun,
    ForecastResponse,
)

from app.services.forecast_history import (
    build_forecast_history_response,
    build_forecast_history_responses,
    get_forecast_history,
    get_forecast_history_run,
    get_latest_forecast_history_run,
)

from app.services.forecasting import (
    generate_forecast,
    get_forecast,
)

from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(
    prefix="/api/forecast",
    tags=["Forecast"],
)


@router.get(
    "",
    response_model=ForecastResponse,
    summary="Get production forecast",
)
def forecast(
    db: Session = Depends(get_db),
):
    return get_forecast(db)

@router.post(
    "/generate",
    response_model=ForecastResponse,
    summary="Generate and save production forecast",
)
def generate(
    db: Session = Depends(get_db),
):
    return generate_forecast(db)

@router.get(
    "/history",
    response_model=list[ForecastHistoryRun],
    summary="Get forecast history",
)
def history(
    db: Session = Depends(get_db),
):
    runs = get_forecast_history(db)

    return build_forecast_history_responses(runs)


@router.get(
    "/history/latest",
    response_model=ForecastHistoryRun,
    summary="Get latest forecast history",
)
def latest_history(
    db: Session = Depends(get_db),
):
    run = get_latest_forecast_history_run(db)

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="No forecast history found",
        )

    return build_forecast_history_response(run)


@router.get(
    "/history/{run_id}",
    response_model=ForecastHistoryRun,
    summary="Get forecast history run",
)
def history_run(
    run_id: int,
    db: Session = Depends(get_db),
):
    run = get_forecast_history_run(
        db,
        run_id,
    )

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="Forecast history run not found",
        )

    return build_forecast_history_response(run)
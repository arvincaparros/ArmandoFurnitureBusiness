from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from google.genai.errors import APIError

from app.database.connection import get_db

from app.schemas.forecast import (
    ForecastChatRequest,
    ForecastChatResponse,
    ForecastHistoryRun,
    ForecastResponse,
    ForecastTimeSeriesResponse,
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
    get_forecast_timeseries,
)

from app.services.forecast_chat import (
    ChatConfigurationError,
    generate_chat_reply,
)

from app.services.auth import get_current_user

from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(
    prefix="/api/forecast",
    tags=["Forecast"],
    dependencies=[Depends(get_current_user)],
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
    "/timeseries",
    response_model=ForecastTimeSeriesResponse,
    summary="Get monthly historical and forecast series for charting",
)
def timeseries(
    product_id: int | None = None,
    db: Session = Depends(get_db),
):
    result = get_forecast_timeseries(db, product_id)

    if product_id is not None and not result["products"]:
        raise HTTPException(
            status_code=404,
            detail="Product not found",
        )

    return result

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


@router.post(
    "/chat",
    response_model=ForecastChatResponse,
    summary="Ask the demand forecasting assistant a question",
)
def chat(
    data: ForecastChatRequest,
    db: Session = Depends(get_db),
):
    try:
        reply = generate_chat_reply(db, data.message)

    except ChatConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="The forecasting assistant is not available right now.",
        ) from exc

    except APIError as exc:
        raise HTTPException(
            status_code=502,
            detail="The forecasting assistant is temporarily unavailable. Please try again.",
        ) from exc

    return {"reply": reply}


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
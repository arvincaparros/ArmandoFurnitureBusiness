from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.forecast import ForecastResponse
from app.services.forecasting import get_forecast


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
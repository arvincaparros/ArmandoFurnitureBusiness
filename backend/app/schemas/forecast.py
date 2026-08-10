from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ProductForecast(BaseModel):
    product_id: int
    product_name: str
    historical_quantity: Decimal
    forecast_quantity: Decimal
    trend: str


class ForecastResponse(BaseModel):
    forecast_period: str
    products: list[ProductForecast]


class ForecastHistoryResult(BaseModel):
    product_id: int
    historical_quantity: Decimal
    forecast_quantity: Decimal
    trend: str


class ForecastHistoryRun(BaseModel):
    id: int
    forecast_period: str
    created_at: datetime
    products: list[ForecastHistoryResult]


ForecastHistoryRun.model_rebuild()
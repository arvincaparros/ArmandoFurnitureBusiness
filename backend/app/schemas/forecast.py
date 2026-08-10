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
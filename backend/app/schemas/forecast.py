from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductForecast(BaseModel):
    # get_forecast() continues to build its internal dict using
    # historical_quantity/forecast_quantity (unchanged by Phase E -
    # forecast_history.py's persistence path reads those same keys).
    # These aliases translate that internal shape to the Phase E
    # wire contract without touching the service layer.
    model_config = ConfigDict(populate_by_name=True)

    product_id: int
    product_name: str
    historical_sales: Decimal = Field(
        validation_alias="historical_quantity",
    )
    predicted_demand: Decimal = Field(
        validation_alias="forecast_quantity",
    )
    trend: str
    confidence_level: Decimal
    forecast_status: str


class ForecastResponse(BaseModel):
    forecast_period: str
    products: list[ProductForecast]


class ForecastHistoryResult(BaseModel):
    product_id: int
    historical_quantity: Decimal
    forecast_quantity: Decimal
    trend: str
    confidence_level: Decimal | None = None
    forecast_status: str | None = None


class ForecastHistoryRun(BaseModel):
    id: int
    forecast_period: str
    created_at: datetime
    products: list[ForecastHistoryResult]


ForecastHistoryRun.model_rebuild()


class ForecastTimeSeriesPoint(BaseModel):
    # Historical points are one per qualifying sales transaction:
    # "period" is the transaction date (YYYY-MM-DD) and
    # transaction_id/transaction_number identify the record, so
    # transactions sharing a date stay independently identifiable.
    # The trailing forecast point has no transaction, and its
    # "period" is the first day of the forecasted month.
    period: str
    transaction_id: int | None = None
    transaction_number: str | None = None
    historical_sales: Decimal | None = None
    quantity_produced: Decimal | None = None
    predicted_demand: Decimal | None = None
    is_forecast: bool


class ProductTimeSeries(BaseModel):
    product_id: int
    product_name: str
    series: list[ForecastTimeSeriesPoint]


class ForecastTimeSeriesResponse(BaseModel):
    products: list[ProductTimeSeries]


class ForecastChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ForecastChatResponse(BaseModel):
    reply: str

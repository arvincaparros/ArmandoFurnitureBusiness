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
    # point_type is the authoritative kind discriminator:
    #   SALE       - one qualifying sales transaction. "period" is the
    #                transaction date (YYYY-MM-DD), transaction_id/
    #                transaction_number identify the row, and
    #                historical_sales carries the quantity SOLD.
    #                quantity_produced is set only on PRE-ROLLOUT rows
    #                (those with no production_cycle_id) - see
    #                services/forecasting.py for why.
    #   PRODUCTION - one applied production ledger entry. "period" is
    #                the apply date, application_id/
    #                application_number/production_cycle_id identify
    #                it, and quantity_produced carries the units
    #                PRODUCED. This is the authoritative source for
    #                new production.
    #   FORECAST   - the single trailing projection. "period" is the
    #                first day of the forecasted month.
    # is_forecast is kept, unchanged, for every existing consumer: it
    # is True exactly when point_type == "FORECAST".
    period: str
    point_type: str
    transaction_id: int | None = None
    transaction_number: str | None = None
    application_id: int | None = None
    application_number: str | None = None
    production_cycle_id: int | None = None
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

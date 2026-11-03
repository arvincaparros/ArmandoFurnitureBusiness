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
    #   SALE       - one calendar week's sold total (zero-filled).
    #                historical_sales carries the quantity SOLD.
    #                quantity_produced is always None here - produced
    #                figures live on the matching PRODUCTION point for
    #                the same week, never duplicated onto this one.
    #   PRODUCTION - one calendar week's produced total, summed from
    #                every production application applied that week,
    #                plus any pre-rollout (production_cycle_id IS NULL)
    #                sale's own stored quantity_produced for that week
    #                - its only production record, since it predates
    #                the ledger. Never zero-filled: a week with no
    #                production has no PRODUCTION point at all.
    #   FORECAST   - one of the three trailing weekly projections.
    # is_forecast is kept, unchanged, for every existing consumer: it
    # is True exactly when point_type == "FORECAST".
    period: str
    point_type: str
    historical_sales: Decimal | None = None
    quantity_produced: Decimal | None = None
    predicted_demand: Decimal | None = None
    is_forecast: bool


class ProductTimeSeries(BaseModel):
    product_id: int
    product_name: str
    # Computed once from the product's weekly SOLD series and shared
    # by every forecast point in `series` below - never recomputed
    # per point.
    trend: str
    confidence_level: Decimal
    series: list[ForecastTimeSeriesPoint]


class ForecastTimeSeriesResponse(BaseModel):
    products: list[ProductTimeSeries]


class ForecastChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ForecastChatResponse(BaseModel):
    reply: str

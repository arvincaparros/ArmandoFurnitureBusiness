from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

class DashboardSummaryResponse(BaseModel):
    total_products: int
    total_resources: int
    total_production_cycles: int
    total_allocations: int
    total_optimization_runs: int
    latest_optimization_profit: Decimal | None
    total_sales: Decimal
    total_sales_profit: Decimal
    latest_forecast_period: str | None
    latest_forecast_created_at: datetime | None
    latest_forecast_total_quantity: Decimal | None

    
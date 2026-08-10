from decimal import Decimal

from pydantic import BaseModel


class DashboardSummaryResponse(BaseModel):
    total_products: int
    total_resources: int
    total_production_cycles: int
    total_allocations: int
    total_optimization_runs: int
    latest_optimization_profit: Decimal | None
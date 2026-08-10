from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class OptimizationHistoryResult(BaseModel):
    id: int
    product_id: int
    recommended_quantity: Decimal
    unit_profit: Decimal
    total_profit: Decimal


class OptimizationHistoryResponse(BaseModel):
    id: int
    production_cycle_id: int
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    status: str
    objective_value: Decimal | None
    total_profit: Decimal | None
    results: list[OptimizationHistoryResult]
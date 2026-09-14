from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class OptimizationHistoryResult(BaseModel):
    id: int
    product_id: int
    recommended_quantity: Decimal
    unit_profit: Decimal
    total_profit: Decimal
    # Revision #4: additive, backward-compatible fields - read off the
    # OptimizationResult ORM row's own minimum_demand/shortfall
    # properties (app/database/models.py), not persisted separately.
    minimum_demand: Decimal
    shortfall: Decimal


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
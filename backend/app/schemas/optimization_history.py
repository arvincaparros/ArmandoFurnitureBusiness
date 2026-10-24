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
    # Null forever for any run saved before this field existed - never
    # backfilled from current prices (see OptimizationRun.total_cost).
    total_cost: Decimal | None
    # The imported aggregate unit count, set only on a summary-only
    # record; null for a native run, whose Products Produced is derived
    # client-side from the results below.
    products_produced: int | None
    # True when this run carries aggregate figures only and has no
    # per-product results - the client must never treat it as an
    # applyable plan, and the backend rejects it on Apply.
    is_summary_only: bool
    results: list[OptimizationHistoryResult]
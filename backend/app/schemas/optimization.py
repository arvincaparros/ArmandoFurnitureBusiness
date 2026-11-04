from decimal import Decimal

from enum import Enum

from pydantic import BaseModel


class OptimizationObjective(str, Enum):
    MAX_PROFIT = "MAX_PROFIT"


class PlanningMode(str, Enum):
    # production.py::optimize_production builds a forecast dict from
    # get_forecast() and passes it to solve_optimization(), which caps
    # each product at its forecast ceiling via
    # add_forecast_constraints(). Still fully supported, just no
    # longer the default - a caller must now explicitly ask for it.
    DEMAND_BASED = "demand_based"
    # Same solve_optimization() call, same resource/BOM/minimum-demand
    # constraints - only difference is production.py passes
    # forecast=None, so add_forecast_constraints() never runs and no
    # product is capped by sales forecast. Default: a caller that
    # doesn't send planning_mode at all now gets this, not
    # DEMAND_BASED.
    RESOURCE_BASED = "resource_based"


class OptimizationRequest(BaseModel):
    objective: OptimizationObjective = OptimizationObjective.MAX_PROFIT
    planning_mode: PlanningMode = PlanningMode.RESOURCE_BASED


class OptimizationAllocation(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    unit_profit: Decimal
    total_profit: Decimal
    # Revision #4: additive fields, backward-compatible with any
    # existing consumer that only reads the fields above -
    # minimum_demand is 0 for a product with no minimum, and shortfall
    # is 0 whenever quantity already meets it (see
    # app/services/optimization.py::solve_optimization/
    # apply_optimization for how these are computed).
    minimum_demand: Decimal
    shortfall: Decimal


class OptimizationResourceUsage(BaseModel):
    resource_id: int
    resource_name: str
    unit: str
    required_quantity: Decimal
    available_quantity: Decimal
    # Already consumed by earlier applications THIS cycle, before this
    # plan - 0 when nothing has been applied yet, or for a caller that
    # has not supplied already_consumed_by_resource_id (see
    # calculate_optimized_resource_usage). remaining_quantity below is
    # cumulative: available_quantity - consumed_quantity -
    # required_quantity.
    consumed_quantity: Decimal
    remaining_quantity: Decimal


class OptimizationBottleneck(BaseModel):
    resource_id: int
    resource_name: str
    unit: str
    remaining_quantity: Decimal
    is_binding: bool
    shortage_quantity: Decimal


class OptimizationResponse(BaseModel):
    cycle_id: int
    status: str
    objective: str
    # Which mode produced THIS result - set by optimize_production from
    # the request it just handled. None for apply_production_optimization's
    # response: apply_optimization() only replays an existing
    # OptimizationRun's already-solved allocations, and planning_mode is
    # not persisted (see optimize_production's own comment), so Apply has
    # no mode to report here. Also None for any history-sourced read.
    planning_mode: str | None = None
    total_revenue: Decimal
    total_cost: Decimal
    total_profit: Decimal
    allocations: list[OptimizationAllocation]
    resource_usage: list[OptimizationResourceUsage]
    bottlenecks: list[OptimizationBottleneck]
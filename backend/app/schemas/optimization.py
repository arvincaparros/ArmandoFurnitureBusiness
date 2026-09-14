from decimal import Decimal

from enum import Enum

from pydantic import BaseModel


class OptimizationObjective(str, Enum):
    MAX_PROFIT = "MAX_PROFIT"


class OptimizationRequest(BaseModel):
    objective: OptimizationObjective = OptimizationObjective.MAX_PROFIT


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
    total_revenue: Decimal
    total_cost: Decimal
    total_profit: Decimal
    allocations: list[OptimizationAllocation]
    resource_usage: list[OptimizationResourceUsage]
    bottlenecks: list[OptimizationBottleneck]
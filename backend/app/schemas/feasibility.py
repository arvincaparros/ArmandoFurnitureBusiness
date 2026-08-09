from decimal import Decimal

from pydantic import BaseModel


class ResourceFeasibility(BaseModel):
    resource_id: int
    resource_name: str
    unit: str
    required_quantity: Decimal
    available_quantity: Decimal
    remaining_quantity: Decimal
    is_feasible: bool


class ResourceBottleneck(BaseModel):
    resource_id: int
    resource_name: str
    unit: str
    shortage_quantity: Decimal


class ProductionFeasibilityResponse(BaseModel):
    cycle_id: int
    is_feasible: bool
    resources: list[ResourceFeasibility]
    bottlenecks: list[ResourceBottleneck]
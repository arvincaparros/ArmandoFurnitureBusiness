from decimal import Decimal

from pydantic import BaseModel


class ResourceUtilizationItem(BaseModel):
    resource_id: int
    resource_name: str
    resource_type: str
    unit: str
    available_quantity: Decimal
    consumed_quantity: Decimal
    remaining_quantity: Decimal
    utilization_rate: Decimal
    # "normal" | "high" | "at_risk" | "bottleneck" - four-tier capacity
    # status classified from utilization_rate (see
    # resource_utilization.py::classify_utilization_status). Not a
    # plain str Literal to avoid coupling this schema to the exact
    # tier set changing in lockstep with the service layer.
    status: str


class ResourceUtilizationBottleneck(BaseModel):
    resource_id: int
    resource_name: str
    unit: str
    remaining_quantity: Decimal
    is_binding: bool
    shortage_quantity: Decimal


class ResourceUtilizationResponse(BaseModel):
    cycle_id: int

    # Retained for backward compatibility - both blend incompatible
    # units (kg + hours + pcs) into one ratio/quantity and are no
    # longer displayed as the primary metric. Prefer
    # most_constrained_resource and material_resource_count below.
    overall_utilization_rate: Decimal
    total_raw_materials_consumed: Decimal

    total_labor_hours_used: Decimal
    total_labor_hours_capacity: Decimal
    total_machine_hours_used: Decimal
    total_machine_hours_capacity: Decimal

    # Unit-safe replacements for the blended fields above.
    material_resource_count: int
    most_constrained_resource: ResourceUtilizationItem | None
    at_risk_resources: list[ResourceUtilizationItem]

    resources: list[ResourceUtilizationItem]
    bottlenecks: list[ResourceUtilizationBottleneck]

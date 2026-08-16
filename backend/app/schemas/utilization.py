from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


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


# ---------------------------------------------------------------
# Resource Utilization History - immutable snapshots created when
# "Apply to Production" succeeds (see resource_utilization_history.py
# and optimization.py::apply_optimization). Distinct from
# ResourceUtilizationItem above: these fields are read directly off
# ResourceUtilizationHistoryItem's own stored columns, never
# recalculated from current Resource/CycleResource data.
# ---------------------------------------------------------------

class ResourceUtilizationHistoryItemResponse(BaseModel):
    id: int
    resource_id: int | None
    resource_name: str
    resource_type: str
    unit: str
    available_quantity: Decimal
    consumed_quantity: Decimal
    remaining_quantity: Decimal
    utilization_rate: Decimal
    status: str

    model_config = ConfigDict(
        from_attributes=True,
    )


class ResourceUtilizationRunResponse(BaseModel):
    id: int
    utilization_number: str
    production_cycle_id: int
    generated_at: datetime
    items: list[ResourceUtilizationHistoryItemResponse]

    model_config = ConfigDict(
        from_attributes=True,
    )


# Lightweight list-view shape - omits per-resource items[] so the
# history list endpoint doesn't repeat the same id/date across N rows
# (see resource_utilization_history.py::summarize_utilization_run).
# Use GET .../history/{id} for the full ResourceUtilizationRunResponse.
class ResourceUtilizationRunSummaryResponse(BaseModel):
    id: int
    utilization_number: str
    production_cycle_id: int
    generated_at: datetime
    resource_count: int
    bottleneck_count: int
    at_risk_count: int

from decimal import Decimal

from pydantic import BaseModel


class WeekReferenceResourceSummary(BaseModel):
    available: Decimal
    consumed: Decimal | None
    unit: str
    name: str


class WeekReferenceSummaryResponse(BaseModel):
    week: int
    is_verified: bool
    resources: dict[str, WeekReferenceResourceSummary]
    reference_allocation: dict[str, int]
    reference_total: int
    reference_profit: Decimal


class WeekReferenceCompareRequest(BaseModel):
    resource_overrides: dict[str, Decimal] | None = None


class ResourceUsageRow(BaseModel):
    available: Decimal
    consumed: Decimal
    remaining: Decimal
    utilization_rate: Decimal


class WeekReferenceCompareResponse(BaseModel):
    week: int
    is_modified_input: bool
    reference_match_status: str
    resources_used: dict[str, Decimal]
    resource_usage: dict[str, ResourceUsageRow]
    status: str
    computed_allocation: dict[str, int]
    reference_allocation: dict[str, int]
    allocation_difference: dict[str, int]
    allocation_matches_reference: bool
    computed_total: int
    reference_total: int
    computed_profit: Decimal
    reference_profit: Decimal
    profit_matches_reference: bool

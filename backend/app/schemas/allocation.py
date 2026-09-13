from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductionAllocationCreate(BaseModel):
    product_id: int = Field(
        ...,
        gt=0,
    )

    quantity: Decimal = Field(
        ...,
        gt=0,
        decimal_places=4,
        max_digits=12,
    )


class ProductionAllocationUpdate(BaseModel):
    quantity: Decimal = Field(
        ...,
        gt=0,
        decimal_places=4,
        max_digits=12,
    )


class ProductionAllocationResponse(BaseModel):
    id: int
    production_cycle_id: int
    product_id: int
    quantity: Decimal

    model_config = ConfigDict(
        from_attributes=True,
    )


# GET /{cycle_id}/allocations only (list_allocations) - NOT used by
# create/update/delete, which keep returning the plain
# ProductionAllocationResponse above unchanged. total_cost/total_profit
# are None when any non-labor requirement for the product can't be
# fully and reliably priced right now (inactive resource, or no
# CycleResource price this cycle) - see
# services/allocation.py::get_allocations_with_financials for why that
# never collapses to a silent 0, matching Revision #1's rule.
# total_revenue is never None: Product.selling_price is a required,
# always-positive field.
class ProductionAllocationFinancialsResponse(BaseModel):
    id: int
    production_cycle_id: int
    product_id: int
    quantity: Decimal
    total_revenue: Decimal
    total_cost: Decimal | None
    total_profit: Decimal | None
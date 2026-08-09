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
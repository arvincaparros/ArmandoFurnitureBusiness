from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, computed_field

from decimal import Decimal

from pydantic import Field


class ProductionCycleStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ProductionCycleBase(BaseModel):
    cycle_date: datetime
    start_date: datetime
    end_date: datetime
    status: ProductionCycleStatus = ProductionCycleStatus.OPEN


class ProductionCycleCreate(ProductionCycleBase):
    pass


class ProductionCycleUpdate(BaseModel):
    cycle_date: datetime | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: ProductionCycleStatus | None = None


class ProductionCycleResponse(ProductionCycleBase):
    id: int

    model_config = ConfigDict(
        from_attributes=True,
    )

class CycleResourceCreate(BaseModel):
    resource_id: int = Field(
        ...,
        gt=0,
    )

    available_quantity: Decimal = Field(
        ...,
        gt=0,
        decimal_places=4,
        max_digits=12,
    )

    # Labor resources are exempt from the positive-price rule enforced
    # below (ge=0, not gt=0) - product labor cost is tracked separately
    # via Product.labor_cost, so a Labor CycleResource's unit_price is
    # allowed to be 0. Non-labor resources still require > 0; that
    # check is done in app.services.cycle_resource, which has access
    # to the resource's resource_type (not present on this schema).
    unit_price: Decimal = Field(
        ...,
        ge=0,
        decimal_places=4,
        max_digits=12,
    )


class CycleResourceUpdate(BaseModel):
    available_quantity: Decimal | None = Field(
        default=None,
        gt=0,
        decimal_places=4,
        max_digits=12,
    )

    # See CycleResourceCreate.unit_price - same Labor exception,
    # enforced in app.services.cycle_resource.
    unit_price: Decimal | None = Field(
        default=None,
        ge=0,
        decimal_places=4,
        max_digits=12,
    )


class CycleResourceResponse(BaseModel):
    id: int
    production_cycle_id: int
    resource_id: int
    available_quantity: Decimal
    unit_price: Decimal

    model_config = ConfigDict(
        from_attributes=True,
    )

    @computed_field
    @property
    def total_value(self) -> Decimal:
        return self.available_quantity * self.unit_price
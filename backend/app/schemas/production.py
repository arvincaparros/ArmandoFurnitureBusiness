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

    unit_price: Decimal = Field(
        ...,
        gt=0,
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

    unit_price: Decimal | None = Field(
        default=None,
        gt=0,
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
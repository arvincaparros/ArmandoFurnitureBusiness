from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProductionApplicationItemResponse(BaseModel):
    product_id: int
    quantity_produced: Decimal

    model_config = ConfigDict(from_attributes=True)


class ProductionApplicationResourceItemResponse(BaseModel):
    # Nullable because the FK is ON DELETE SET NULL - resource_name
    # and unit are denormalised precisely so the row stays displayable
    # when this is None.
    resource_id: int | None
    resource_name: str
    unit: str
    consumed_quantity: Decimal

    model_config = ConfigDict(from_attributes=True)


class ProductionApplicationResponse(BaseModel):
    id: int
    application_number: str
    production_cycle_id: int
    optimization_run_id: int
    applied_at: datetime
    product_items: list[ProductionApplicationItemResponse]
    resource_items: list[
        ProductionApplicationResourceItemResponse
    ]

    model_config = ConfigDict(from_attributes=True)

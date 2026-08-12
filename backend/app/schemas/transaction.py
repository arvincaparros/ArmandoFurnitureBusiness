from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class SalesTransactionCreate(BaseModel):
    product_id: int
    transaction_date: datetime
    quantity_produced: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(gt=0)
    production_cost: Decimal = Field(ge=0)


class SalesTransactionUpdate(BaseModel):
    transaction_date: datetime | None = None

    quantity_produced: Decimal | None = Field(
        default=None,
        gt=0,
    )

    quantity: Decimal | None = Field(
        default=None,
        gt=0,
    )

    unit_price: Decimal | None = Field(
        default=None,
        gt=0,
    )

    production_cost: Decimal | None = Field(
        default=None,
        ge=0,
    )


class SalesTransactionResponse(BaseModel):
    id: int
    transaction_number: str
    product_id: int
    transaction_date: datetime
    quantity_produced: Decimal
    quantity: Decimal
    unit_price: Decimal
    total_sales: Decimal
    production_cost: Decimal
    unit_profit: Decimal
    total_profit: Decimal
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }
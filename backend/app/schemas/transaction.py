from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class SalesTransactionCreate(BaseModel):
    product_id: int
    transaction_date: datetime
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(gt=0)
    unit_profit: Decimal


class SalesTransactionUpdate(BaseModel):
    transaction_date: datetime | None = None
    quantity: Decimal | None = Field(
        default=None,
        gt=0,
    )
    unit_price: Decimal | None = Field(
        default=None,
        gt=0,
    )
    unit_profit: Decimal | None = None


class SalesTransactionResponse(BaseModel):
    id: int
    product_id: int
    transaction_date: datetime
    quantity: Decimal
    unit_price: Decimal
    total_sales: Decimal
    unit_profit: Decimal
    total_profit: Decimal
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }
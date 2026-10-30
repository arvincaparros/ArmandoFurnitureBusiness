from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class SalesTransactionCreate(BaseModel):
    product_id: int
    transaction_date: datetime
    quantity_produced: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(gt=0)
    # Per-unit production cost - app/services/transaction.py::
    # calculate_transaction_values multiplies this by quantity_produced
    # before storing/returning it as the TOTAL production_cost (see
    # SalesTransactionResponse.production_cost below).
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

    # Per-unit, same as SalesTransactionCreate.production_cost - see
    # its comment. When omitted, app/services/transaction.py::
    # update_transaction reconstructs the per-unit rate from the
    # existing stored total rather than reusing the total as-is.
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
    # TOTAL production cost for this transaction (quantity_produced x
    # the per-unit rate submitted in the request) - not per-unit. See
    # SalesTransactionCreate.production_cost.
    production_cost: Decimal
    unit_profit: Decimal
    total_profit: Decimal
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class TransactionRangeMode(str, Enum):
    """
    Which rule produced the window the response was filtered by.

    LATEST_AVAILABLE is the default when the caller sends no params:
    the window is derived from the stored data (the 7 most recent
    distinct transaction dates), never from the caller's clock.
    """

    LATEST_AVAILABLE = "latest_available"
    CUSTOM = "custom"
    ALL = "all"


class TransactionDateRange(BaseModel):
    """
    The window actually applied to this response - what the client is
    looking at. Deliberately distinct from TransactionAvailableRange
    (what EXISTS in the table): filtering against `available` instead
    of `start_date`/`end_date` would silently widen the view.

    Either bound may be null, and only in CUSTOM mode: a caller may
    send start_date alone (open-ended future) or end_date alone (open
    -ended past). In LATEST_AVAILABLE mode both bounds are always
    set, because the window is resolved from real rows - if there are
    no rows there is no window at all and the whole object is null.
    """

    start_date: date | None
    end_date: date | None
    mode: TransactionRangeMode


class TransactionAvailableRange(BaseModel):
    """
    The full span of transaction_date present in the table,
    regardless of the active window - drives the date inputs' min/max
    and the "no transactions in this range" empty state. Null only
    when the table is empty.
    """

    earliest: date
    latest: date


class SalesTransactionListResponse(BaseModel):
    """
    Wraps what used to be a bare list. The client cannot label or
    empty-state a window it did not choose, so the server reports the
    window it resolved alongside the rows.
    """

    items: list[SalesTransactionResponse]
    total: int
    range: TransactionDateRange | None
    available: TransactionAvailableRange | None

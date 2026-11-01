from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ProductInventoryResponse(BaseModel):
    product_id: int
    product_name: str

    # Declared opening balance from the REVIEWED opening inventory
    # set; 0 when none was declared for this product.
    opening_quantity: Decimal

    # All-cycles ledger totals - the two halves of available_stock
    # alongside opening_quantity.
    total_produced: Decimal
    total_sold: Decimal

    # opening + total_produced - total_sold, floored at zero. The
    # actual on-hand figure, spanning every cycle.
    available_stock: Decimal

    # CURRENT cycle only. These two reset to zero when a new cycle
    # starts; available_stock above does not.
    cycle_produced: Decimal
    cycle_sold: Decimal


class InventoryOverviewResponse(BaseModel):
    # Null when no production cycle exists yet, in which case every
    # cycle_* figure above is 0.
    cycle_id: int | None
    cycle_start_date: datetime | None
    cycle_end_date: datetime | None

    # False until a COMPLETE opening inventory set has been reviewed.
    #
    # [AMENDMENT A] While false, sales are REFUSED (409) - not
    # recorded unvalidated. The original comment here said the
    # opposite ("sales are NOT validated against stock"), which
    # described the soft gate Amendment A rejected; it arrived with
    # this file's verbatim transcription from the plan in G4 and is
    # corrected here because the frontend reads this field to decide
    # what to TELL the user, and the old wording would have produced
    # a banner contradicting the API.
    #
    # Comment only - the field, its type and its value are unchanged.
    stock_validation_enabled: bool

    products: list[ProductInventoryResponse]

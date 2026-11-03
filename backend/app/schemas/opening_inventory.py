from datetime import datetime
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class OpeningInventoryItemInput(BaseModel):
    product_id: int = Field(..., gt=0)

    # ge=0, not gt=0: declaring a product as explicitly zero is a real
    # and meaningful statement ("I counted, there are none"), distinct
    # from omitting it.
    quantity: Decimal = Field(
        ...,
        ge=0,
        decimal_places=4,
        max_digits=12,
    )

    notes: str | None = Field(default=None, max_length=500)


class OpeningInventoryItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: Decimal
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


def _require_unique_products(
    items: list[OpeningInventoryItemInput],
) -> list[OpeningInventoryItemInput]:
    """
    Rejected at the edge rather than left to the database's
    uq_opening_inventory_item constraint, so the caller gets a 422
    naming the problem instead of a 400 from an IntegrityError whose
    message exposes the constraint name.
    """

    product_ids = [item.product_id for item in items]

    if len(product_ids) != len(set(product_ids)):
        raise ValueError(
            "each product may appear at most once in an opening "
            "inventory set"
        )

    return items


class OpeningInventorySetCreate(BaseModel):
    effective_date: datetime
    notes: str | None = Field(default=None, max_length=500)
    items: list[OpeningInventoryItemInput] = Field(
        default_factory=list,
    )

    @model_validator(mode="after")
    def _validate_items(self):
        _require_unique_products(self.items)

        return self


class OpeningInventorySetUpdate(BaseModel):
    """
    DRAFT sets only - enforced in the service, not here, because the
    status lives on the row rather than in the request. `items`, when
    sent, REPLACES the whole item list: a partial per-item merge would
    make "remove this product's declared balance" inexpressible.
    """

    effective_date: datetime | None = None
    notes: str | None = Field(default=None, max_length=500)
    items: list[OpeningInventoryItemInput] | None = None

    @model_validator(mode="after")
    def _validate_items(self):
        if self.items is not None:
            _require_unique_products(self.items)

        return self


class OpeningInventorySetResponse(BaseModel):
    id: int
    set_number: str
    status: str
    effective_date: datetime
    notes: str | None
    created_at: datetime
    reviewed_at: datetime | None
    items: list[OpeningInventoryItemResponse]

    # Usernames rather than raw ids: the audit trail is read by a
    # human, and the frontend has no user-lookup endpoint. None when
    # the user row was deleted (FK is ON DELETE SET NULL) or when the
    # action predates the column.
    #
    # Explicit fields, not computed_field properties reading
    # self.created_by / self.reviewed_by: Pydantic v2's
    # from_attributes validation only copies DECLARED fields off the
    # ORM object, so an undeclared `created_by`/`reviewed_by`
    # attribute is never actually present on the built model and a
    # computed_field reading it always resolves to None (confirmed by
    # test_create_draft_then_review_enables_stock_validation's
    # `reviewed_by_username is not None` assertion failing under that
    # approach). These are populated explicitly in the router instead,
    # via _to_response(), which reads the ORM relationship directly.
    created_by_username: str | None = None
    reviewed_by_username: str | None = None

    model_config = ConfigDict(from_attributes=True)


class OpeningInventoryStatusResponse(BaseModel):
    """
    The single question every stock-aware screen needs answered before
    it can show or enforce anything: has opening inventory been
    reviewed yet, and if so, what does it say?
    """

    stock_validation_enabled: bool
    reviewed_set: OpeningInventorySetResponse | None
    draft_set: OpeningInventorySetResponse | None

from decimal import Decimal
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
)


def _require_whole_units(value: Decimal) -> Decimal:
    """
    minimum_demand is a count of units the ILP must produce, so only
    whole numbers are accepted through the API even though the column
    itself is Numeric(12, 4). This is not merely cosmetic: a
    fractional minimum makes optimization.py::
    _is_minimum_demand_vector_feasible's continuous feasibility
    witness disagree with create_decision_variables' INTEGER lowBound,
    which silently diverts an otherwise Phase 1 (hard-minimum) solve
    into the Phase 2 adaptive path (see solve_optimization's own note
    on that gap). Rejecting fractions at the edge keeps that gap
    unreachable from the API. Compared against to_integral_value()
    rather than Field(decimal_places=0) so an equivalent whole value
    written with a trailing zero ("4.0", as some JSON clients emit) is
    still accepted - it is the same number of units.
    """

    if value != value.to_integral_value():
        raise ValueError(
            "minimum_demand must be a whole number of units"
        )

    return value


# Shared by ProductCreate and ProductUpdate so the two can never
# drift apart. Deliberately NOT placed on ProductBase: ProductResponse
# inherits ProductBase, and minimum_demand must stay REQUIRED there
# (the column is NOT NULL and every response really does carry a
# value) - giving it a default on ProductBase would weaken that
# response contract, while making it required on ProductBase would
# make it mandatory on create and break every existing caller that
# omits it.
MinimumDemand = Annotated[
    Decimal,
    Field(
        ge=0,
        le=1_000_000,
        max_digits=12,
    ),
    AfterValidator(_require_whole_units),
]


class ProductBase(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=150,
    )

    selling_price: Decimal = Field(
        ...,
        gt=0,
        decimal_places=2,
        max_digits=12,
    )

    # Per-product labor cost (client cost model - see
    # app/database/models.py::Product.labor_cost). Required, like
    # selling_price, so every product has a real value rather than a
    # silently-assumed 0.
    labor_cost: Decimal = Field(
        ...,
        ge=0,
        decimal_places=2,
        max_digits=12,
    )

    is_active: bool = True


class ProductCreate(ProductBase):
    # Optional with a 0 default (0 = "no minimum", a real and common
    # value - three seeded products legitimately hold it), so an
    # existing caller that omits the field keeps creating products
    # exactly as before rather than getting a 422.
    minimum_demand: MinimumDemand = Decimal("0")


class ProductUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )

    selling_price: Decimal | None = Field(
        default=None,
        gt=0,
        decimal_places=2,
        max_digits=12,
    )

    labor_cost: Decimal | None = Field(
        default=None,
        ge=0,
        decimal_places=2,
        max_digits=12,
    )

    # None means "leave unchanged" - update_product() dumps with
    # exclude_unset=True, so an explicit 0 is still persisted as 0 and
    # is never confused with an omitted field.
    minimum_demand: MinimumDemand | None = None

    is_active: bool | None = None


class ProductResponse(ProductBase):
    id: int

    # Required, never optional: the column is NOT NULL, so every
    # product genuinely has a value and a response must always carry
    # it. Writable since the Product Data Management revision via
    # ProductCreate/ProductUpdate above (see optimization.py::
    # create_decision_variables for where the ILP reads it) - but
    # declared here rather than on ProductBase precisely so that
    # "required on the way out, optional on the way in" stays
    # expressible.
    minimum_demand: Decimal

    model_config = ConfigDict(
        from_attributes=True,
    )

class ProductResourceRequirementCreate(BaseModel):
    resource_id: int = Field(
        ...,
        gt=0,
    )

    quantity_required: Decimal = Field(
        ...,
        gt=0,
        decimal_places=4,
        max_digits=12,
    )


class ProductResourceRequirementUpdate(BaseModel):
    quantity_required: Decimal = Field(
        ...,
        gt=0,
        decimal_places=4,
        max_digits=12,
    )


class ProductResourceRequirementResponse(BaseModel):
    id: int
    product_id: int
    resource_id: int
    quantity_required: Decimal

    model_config = ConfigDict(
        from_attributes=True,
    )
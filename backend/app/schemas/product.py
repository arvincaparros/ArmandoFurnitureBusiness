from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


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

    is_active: bool = True


class ProductCreate(ProductBase):
    pass


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

    is_active: bool | None = None


class ProductResponse(ProductBase):
    id: int

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
from pydantic import BaseModel, ConfigDict, Field


class ResourceBase(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    resource_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )

    unit: str = Field(
        ...,
        min_length=1,
        max_length=30,
    )

    is_active: bool = True


class ResourceCreate(ResourceBase):
    pass


class ResourceUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    resource_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    unit: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )

    is_active: bool | None = None


class ResourceResponse(ResourceBase):
    id: int

    model_config = ConfigDict(
        from_attributes=True,
    )
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )

    password: str = Field(
        ...,
        min_length=1,
    )


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    username: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )

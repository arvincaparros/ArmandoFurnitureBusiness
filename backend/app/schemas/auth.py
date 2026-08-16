import re
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

# No email-validator/EmailStr dependency is installed (confirmed:
# `pip show email-validator` finds nothing) - a small regex check
# avoids pulling in a new dependency for the smallest change that
# does the job. Not RFC 5322-complete, just enough to reject obvious
# nonsense ("not-an-email").
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# The application's password policy - defined here since none
# existed before this feature. Kept intentionally simple: minimum
# length only, applied identically everywhere a new password is set
# (registration, reset, change).
PASSWORD_MIN_LENGTH = 8


def _validate_password_policy(value: str) -> str:
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"
        )

    return value


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
    email: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class MessageResponse(BaseModel):
    detail: str


class RegisterRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_.-]+$",
    )

    email: str = Field(
        ...,
        min_length=3,
        max_length=255,
    )

    password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=128,
    )

    confirm_password: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        if not EMAIL_PATTERN.match(value):
            raise ValueError("Enter a valid email address")

        return value.lower()

    @field_validator("password")
    @classmethod
    def validate_password_policy(cls, value: str) -> str:
        return _validate_password_policy(value)

    @model_validator(mode="after")
    def validate_passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")

        return self


class ForgotPasswordRequest(BaseModel):
    email: str = Field(
        ...,
        min_length=3,
        max_length=255,
    )

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        if not EMAIL_PATTERN.match(value):
            raise ValueError("Enter a valid email address")

        return value.lower()


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)

    new_password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=128,
    )

    confirm_password: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    @field_validator("new_password")
    @classmethod
    def validate_password_policy(cls, value: str) -> str:
        return _validate_password_policy(value)

    @model_validator(mode="after")
    def validate_passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")

        return self


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)

    new_password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=128,
    )

    confirm_password: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    @field_validator("new_password")
    @classmethod
    def validate_password_policy(cls, value: str) -> str:
        return _validate_password_policy(value)

    @model_validator(mode="after")
    def validate_passwords_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")

        if self.new_password == self.current_password:
            raise ValueError(
                "New password must be different from the current password"
            )

        return self

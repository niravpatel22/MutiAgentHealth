"""Auth, user, and business-profile request/response models."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import PASSWORD_MAX_LENGTH
from app.db.models import Role


def _normalize_email(value: str) -> str:
    return value.strip().lower()


class _EmailNormalizer(BaseModel):
    @field_validator("email", check_fields=False)
    @classmethod
    def _normalize(cls, value: str) -> str:
        return _normalize_email(value)


class RegisterRequest(_EmailNormalizer):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(examples=["manager@hospital.example"])
    password: str = Field(
        min_length=1, max_length=PASSWORD_MAX_LENGTH, examples=["Correct-Horse-Battery-9"]
    )


class LoginRequest(_EmailNormalizer):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(examples=["manager@hospital.example"])
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    role: Role
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str = Field(description="Short-lived JWT. Keep in memory only; never persist.")
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int = Field(description="Access token lifetime in seconds", examples=[900])
    user: UserOut


class AdminUserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Role | None = None
    is_active: bool | None = None


class BusinessProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    company_name: str = Field(
        min_length=1, max_length=200, examples=["Sunrise Multispeciality Hospital"]
    )
    industry: str = Field(default="Healthcare", min_length=1, max_length=100)
    team_size: int = Field(ge=1, le=1_000_000, examples=[250])
    business_goals: str = Field(
        default="", max_length=2000, examples=["Reduce no-shows and wait times"]
    )


class BusinessProfileOut(BusinessProfileIn):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime | None

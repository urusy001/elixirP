from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ---------- Base ----------

class UserBase(BaseModel):
    tg_phone: str | None = Field(
        None,
        description="Telegram phone number of the user (if provided by Telegram)",
    )
    name: str | None = Field(
        None,
        description="First name of the user",
    )
    surname: str | None = Field(
        None,
        description="Last name of the user",
    )
    email: EmailStr | None = Field(
        None,
        description="User email address",
    )
    phone: str | None = Field(
        None,
        description="Additional phone number / contact phone",
    )
    photo_url: str | None = Field(
        None,
        description="User photo URL",
    )
    thread_id: str | None = Field(
        None,
        description="Associated OpenAI thread ID",
    )
    premium_requests: float = Field(
        0,
        ge=0,
        description="How many premium model requests the user has",
    )
    premium_until: datetime | None = Field(None, description="Updated premium until")
    input_tokens: int = Field(
        0,
        ge=0,
        description="Total number of input tokens used by the user",
    )
    output_tokens: int = Field(
        0,
        ge=0,
        description="Total number of output tokens used by the user",
    )
    blocked_until: datetime | None = Field(
        None,
        description="User blocked until this datetime",
    )


class UserCreate(UserBase):
    """Schema used when creating a new user."""
    tg_id: int = Field(..., description="Telegram user ID")
    tg_ref_id: int | None = Field(
        None,
        description="Optional referral user ID",
    )


class UserUpdate(BaseModel):
    """Schema used when updating existing user fields."""
    tg_phone: str | None = None
    name: str | None = None
    surname: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    photo_url: str | None = None
    thread_id: str | None = None
    premium_requests: float | None = Field(
        None,
        description="Updated premium requests counter",
    )
    premium_until: datetime | None = Field(None, description="Updated premium until")
    input_tokens: int | None = None
    output_tokens: int | None = None
    blocked_until: datetime | None = None
    tg_ref_id: int | None = None


class UserRead(UserBase):
    """Schema used when returning a user from the database."""
    tg_id: int
    tg_ref_id: int | None = None

    model_config = {
        "from_attributes": True,  # ORM mode for SQLAlchemy models
    }
"""User management schemas (admin-facing)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserStatus


class UserCreate(BaseModel):
    """Payload for an admin creating a new user account."""

    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8)
    stake_currency: str = Field("USDT", max_length=16)
    strategy_template_id: int | None = None


class UserOut(BaseModel):
    """User representation returned to admins."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    status: UserStatus
    created_at: datetime

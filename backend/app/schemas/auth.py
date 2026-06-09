"""Authentication request/response schemas."""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Login by email (admin) or username (user) + password."""

    identifier: str = Field(..., description="Admin email or user username")
    password: str


class TokenPair(BaseModel):
    """Access + refresh token pair returned on login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    kind: str  # "admin" or "user"


class RefreshRequest(BaseModel):
    """Exchange a refresh token for a fresh access token."""

    refresh_token: str


class AccessToken(BaseModel):
    """A single freshly minted access token."""

    access_token: str
    token_type: str = "bearer"

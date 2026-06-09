"""Issue and verify the control plane's own session JWTs (admin/user logins).

These tokens are entirely separate from the JWTs of the per-user Freqtrade
instances (the latter are handled by the proxy layer).
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt

from app.config import get_settings

TokenType = Literal["access", "refresh"]
PrincipalKind = Literal["admin", "user"]


class TokenError(ValueError):
    """Raised when a token is invalid, expired or of an unexpected type."""


def create_token(
    *,
    subject_id: int,
    kind: PrincipalKind,
    token_type: TokenType = "access",
) -> str:
    """Create a signed JWT for an admin or user principal.

    :param subject_id: primary-key id of the AdminUser or User row.
    :param kind: ``"admin"`` or ``"user"`` — drives authorization.
    :param token_type: ``"access"`` (short-lived) or ``"refresh"`` (long-lived).
    """
    settings = get_settings()
    now = datetime.now(UTC)
    if token_type == "access":
        expire = now + timedelta(minutes=settings.jwt_access_ttl_minutes)
    else:
        expire = now + timedelta(days=settings.jwt_refresh_ttl_days)

    payload: dict[str, Any] = {
        "sub": str(subject_id),
        "kind": kind,
        "type": token_type,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, *, expected_type: TokenType = "access") -> dict[str, Any]:
    """Decode and validate a control-plane JWT.

    :raises TokenError: if the signature, expiry or token type is invalid.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc

    if payload.get("type") != expected_type:
        raise TokenError(f"Expected {expected_type} token")
    return payload

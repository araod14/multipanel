"""FastAPI authentication/authorization dependencies (RBAC).

Two principal kinds exist, distinguished by the ``kind`` claim in the control-plane
JWT: ``admin`` (operators) and ``user`` (bot owners). Dependencies below resolve the
bearer token to the corresponding ORM row and enforce the required role.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin_user import AdminUser
from app.models.user import User, UserStatus
from app.security.tokens import TokenError, decode_token

_bearer = HTTPBearer(auto_error=True)

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def _decode(creds: HTTPAuthorizationCredentials) -> dict:
    try:
        return decode_token(creds.credentials, expected_type="access")
    except TokenError as exc:
        raise _CREDENTIALS_EXC from exc


def get_current_admin(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminUser:
    """Resolve the bearer token to an :class:`AdminUser`, or raise 401/403."""
    payload = _decode(creds)
    if payload.get("kind") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    admin = db.get(AdminUser, int(payload["sub"]))
    if admin is None:
        raise _CREDENTIALS_EXC
    return admin


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Resolve the bearer token to an active :class:`User`, or raise 401/403."""
    payload = _decode(creds)
    if payload.get("kind") != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User role required")
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise _CREDENTIALS_EXC
    if user.status is UserStatus.suspended:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account suspended")
    return user


CurrentAdmin = Annotated[AdminUser, Depends(get_current_admin)]
CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]

"""Authentication endpoints for both admins and users."""

from fastapi import APIRouter, HTTPException, status

from app.models.admin_user import AdminUser
from app.models.user import User, UserStatus
from app.schemas.auth import AccessToken, LoginRequest, RefreshRequest, TokenPair
from app.security.deps import DbSession
from app.security.passwords import verify_password
from app.security.tokens import TokenError, create_token, decode_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
def login(body: LoginRequest, db: DbSession) -> TokenPair:
    """Authenticate an admin (by email) or a user (by username).

    Admins are tried first; if no admin matches, a user lookup is attempted. A
    generic 401 is returned on any failure to avoid leaking which accounts exist.
    """
    admin = db.query(AdminUser).filter(AdminUser.email == body.identifier).one_or_none()
    if admin is not None and verify_password(body.password, admin.password_hash):
        return _issue(admin.id, "admin")

    user = db.query(User).filter(User.username == body.identifier).one_or_none()
    if user is not None and verify_password(body.password, user.password_hash):
        if user.status is UserStatus.suspended:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account suspended")
        return _issue(user.id, "user")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/refresh", response_model=AccessToken)
def refresh(body: RefreshRequest) -> AccessToken:
    """Exchange a valid refresh token for a new access token."""
    try:
        payload = decode_token(body.refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        ) from exc
    access = create_token(subject_id=int(payload["sub"]), kind=payload["kind"], token_type="access")
    return AccessToken(access_token=access)


def _issue(subject_id: int, kind: str) -> TokenPair:
    return TokenPair(
        access_token=create_token(subject_id=subject_id, kind=kind, token_type="access"),
        refresh_token=create_token(subject_id=subject_id, kind=kind, token_type="refresh"),
        kind=kind,
    )

"""Admin endpoints: user account management.

Bot provisioning (container lifecycle) is wired in Phase 1; here we manage the user
records and audit trail. Creating a user does not yet launch a container.
"""

from fastapi import APIRouter, HTTPException, status

from app.models.bot_instance import BotInstance
from app.models.user import User
from app.schemas.bots import BotInstanceOut
from app.schemas.exchange import BotModeIn, ExchangeCredentialIn, ExchangeCredentialOut
from app.schemas.users import UserCreate, UserOut
from app.security.deps import CurrentAdmin, DbSession
from app.security.passwords import hash_password
from app.services import audit, exchange_creds, provisioning
from app.services.provisioning import LiveModeWithoutKeys

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_user(db: DbSession, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return user


def _require_bot(db: DbSession, user_id: int) -> BotInstance:
    user = _require_user(db, user_id)
    if user.bot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="bot not provisioned")
    return user.bot


@router.get("/users", response_model=list[UserOut])
def list_users(admin: CurrentAdmin, db: DbSession) -> list[User]:
    """Return all users (admin only)."""
    return db.query(User).order_by(User.id).all()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, admin: CurrentAdmin, db: DbSession) -> User:
    """Create a new user account (admin only).

    Provisioning of the user's Freqtrade container happens in a separate step.
    """
    exists = (
        db.query(User)
        .filter((User.username == body.username) | (User.email == body.email))
        .first()
    )
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="username or email already in use"
        )

    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.flush()
    audit.record(
        db,
        actor=f"admin:{admin.id}",
        action="user.create",
        target_user_id=user.id,
        detail=f"username={user.username}",
    )
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, admin: CurrentAdmin, db: DbSession) -> None:
    """Delete a user account (admin only).

    The bot container must be deprovisioned by the provisioning service before this
    is called; cascading removes the bot/credential bookkeeping rows.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    if user.bot is not None:
        provisioning.deprovision_bot(db, user.bot)
    db.delete(user)
    audit.record(db, actor=f"admin:{admin.id}", action="user.delete", target_user_id=user_id)
    db.commit()


# --- Bot lifecycle ---


@router.post("/users/{user_id}/provision", response_model=BotInstanceOut)
def provision(user_id: int, admin: CurrentAdmin, db: DbSession) -> BotInstance:
    """Provision (or re-provision) and start the user's Freqtrade container."""
    user = _require_user(db, user_id)
    instance = provisioning.provision_bot(db, user)
    audit.record(db, actor=f"admin:{admin.id}", action="bot.provision", target_user_id=user_id)
    db.commit()
    db.refresh(instance)
    return instance


@router.post("/users/{user_id}/bot/start", response_model=BotInstanceOut)
def start_bot(user_id: int, admin: CurrentAdmin, db: DbSession) -> BotInstance:
    """Start the user's (already provisioned) container."""
    instance = _require_bot(db, user_id)
    provisioning.start_bot(db, instance)
    audit.record(db, actor=f"admin:{admin.id}", action="bot.start", target_user_id=user_id)
    db.commit()
    db.refresh(instance)
    return instance


@router.post("/users/{user_id}/bot/stop", response_model=BotInstanceOut)
def stop_bot(user_id: int, admin: CurrentAdmin, db: DbSession) -> BotInstance:
    """Stop the user's container without deleting its data."""
    instance = _require_bot(db, user_id)
    provisioning.stop_bot(db, instance)
    audit.record(db, actor=f"admin:{admin.id}", action="bot.stop", target_user_id=user_id)
    db.commit()
    db.refresh(instance)
    return instance


@router.get("/users/{user_id}/bot", response_model=BotInstanceOut)
def get_bot(user_id: int, admin: CurrentAdmin, db: DbSession) -> BotInstance:
    """Return the user's bot instance bookkeeping."""
    return _require_bot(db, user_id)


@router.post("/users/{user_id}/bot/mode", response_model=BotInstanceOut)
def set_mode(user_id: int, body: BotModeIn, admin: CurrentAdmin, db: DbSession) -> BotInstance:
    """Switch the user's bot between dry-run and LIVE trading (re-provisions).

    Enabling live mode (``dry_run=false``) requires stored exchange credentials.
    """
    user = _require_user(db, user_id)
    if user.bot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="bot not provisioned")
    try:
        instance = provisioning.provision_bot(db, user, dry_run=body.dry_run)
    except LiveModeWithoutKeys as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    audit.record(
        db,
        actor=f"admin:{admin.id}",
        action="bot.set_mode",
        target_user_id=user_id,
        detail=f"dry_run={body.dry_run}",
    )
    db.commit()
    db.refresh(instance)
    return instance


@router.post("/users/{user_id}/bot/rotate-credentials", response_model=BotInstanceOut)
def rotate_credentials(user_id: int, admin: CurrentAdmin, db: DbSession) -> BotInstance:
    """Regenerate the bot's REST api_server credentials and recreate the container."""
    user = _require_user(db, user_id)
    if user.bot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="bot not provisioned")
    instance = provisioning.provision_bot(db, user)
    audit.record(
        db, actor=f"admin:{admin.id}", action="bot.rotate_credentials", target_user_id=user_id
    )
    db.commit()
    db.refresh(instance)
    return instance


# --- Exchange credentials (encrypted at rest) ---


@router.put("/users/{user_id}/exchange", response_model=ExchangeCredentialOut)
def set_exchange(
    user_id: int, body: ExchangeCredentialIn, admin: CurrentAdmin, db: DbSession
) -> dict:
    """Set/replace a user's exchange API credentials.

    If the user already has a running bot, it is re-provisioned so the new keys are
    injected. The secrets themselves are never returned or logged.
    """
    user = _require_user(db, user_id)
    cred = exchange_creds.set_credentials(db, user, body)
    if user.bot is not None:
        provisioning.provision_bot(db, user)
    audit.record(
        db,
        actor=f"admin:{admin.id}",
        action="exchange.set",
        target_user_id=user_id,
        detail=f"exchange={body.exchange_name}",
    )
    db.commit()
    return exchange_creds.metadata(cred)


@router.get("/users/{user_id}/exchange", response_model=ExchangeCredentialOut)
def get_exchange(user_id: int, admin: CurrentAdmin, db: DbSession) -> dict:
    """Return non-secret metadata about a user's exchange credentials."""
    user = _require_user(db, user_id)
    if user.exchange_credential is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no exchange credentials")
    return exchange_creds.metadata(user.exchange_credential)


@router.delete("/users/{user_id}/exchange", status_code=status.HTTP_204_NO_CONTENT)
def delete_exchange(user_id: int, admin: CurrentAdmin, db: DbSession) -> None:
    """Delete a user's exchange credentials (forces dry-run on next provision)."""
    user = _require_user(db, user_id)
    if not exchange_creds.delete_credentials(db, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no exchange credentials")
    audit.record(db, actor=f"admin:{admin.id}", action="exchange.delete", target_user_id=user_id)
    db.commit()

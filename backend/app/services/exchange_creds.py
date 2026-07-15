"""Manage a user's encrypted exchange API credentials.

Plaintext secrets enter only through :func:`set_credentials`, are immediately
Fernet-encrypted, and are never read back out except transiently during container
provisioning (see :mod:`app.services.provisioning`).
"""

from sqlalchemy.orm import Session

from app.models.exchange_credential import ExchangeCredential
from app.models.user import User
from app.schemas.exchange import ExchangeCredentialIn, ExchangeName
from app.security import vault

#: Exchanges real credentials may be stored for. Guards the real-money path only; the
#: dry-run fallback (``CP_DEFAULT_EXCHANGE``) is deliberately unconstrained.
SUPPORTED_EXCHANGES: tuple[str, ...] = tuple(e.value for e in ExchangeName)


def set_credentials(db: Session, user: User, payload: ExchangeCredentialIn) -> ExchangeCredential:
    """Create or replace ``user``'s exchange credentials (encrypted at rest)."""
    cred = user.exchange_credential or ExchangeCredential(user_id=user.id)
    cred.exchange_name = payload.exchange_name.value
    cred.key_enc = vault.encrypt(payload.key)
    cred.secret_enc = vault.encrypt(payload.secret)
    cred.password_enc = vault.encrypt(payload.password) if payload.password else None
    cred.uid_enc = vault.encrypt(payload.uid) if payload.uid else None
    if user.exchange_credential is None:
        db.add(cred)
        user.exchange_credential = cred
    db.flush()
    return cred


def metadata(cred: ExchangeCredential) -> dict:
    """Return non-secret metadata for display (key masked to last 4 chars)."""
    key = vault.decrypt(cred.key_enc)
    masked = f"{'•' * max(len(key) - 4, 0)}{key[-4:]}" if key else ""
    return {
        "exchange_name": cred.exchange_name,
        "key_masked": masked,
        "has_password": cred.password_enc is not None,
        "has_uid": cred.uid_enc is not None,
        "updated_at": cred.updated_at,
    }


def delete_credentials(db: Session, user: User) -> bool:
    """Delete ``user``'s exchange credentials. Returns ``True`` if one existed."""
    cred = user.exchange_credential
    if cred is None:
        return False
    db.delete(cred)
    user.exchange_credential = None
    db.flush()
    return True

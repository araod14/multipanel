"""Symmetric secret vault used to encrypt exchange / API secrets at rest.

The master key (``CP_FERNET_KEY``) lives only in the process environment, never in
the database. Plaintext secrets exist only transiently in memory and are injected
into the per-user Freqtrade containers as environment variables at launch time.
"""

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class VaultError(RuntimeError):
    """Raised when encryption or decryption fails."""


def _fernet() -> Fernet:
    key = get_settings().fernet_key
    if not key:
        raise VaultError("CP_FERNET_KEY is not configured")
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise VaultError("CP_FERNET_KEY is not a valid Fernet key") from exc


def encrypt(plaintext: str) -> str:
    """Encrypt ``plaintext`` and return a URL-safe token string for DB storage."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a token produced by :func:`encrypt`.

    :raises VaultError: if the token is invalid or was encrypted with another key.
    """
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise VaultError("Unable to decrypt secret (wrong key or corrupted data)") from exc

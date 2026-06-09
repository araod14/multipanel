"""Password hashing helpers for control-plane admins and users (bcrypt).

Uses the ``bcrypt`` library directly (passlib is unmaintained and breaks against
bcrypt 4.x). bcrypt only considers the first 72 bytes of a password, so inputs are
truncated to that boundary to avoid the ValueError newer bcrypt raises on longer
secrets.
"""

import bcrypt

_MAX_BCRYPT_BYTES = 72


def _to_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_MAX_BCRYPT_BYTES]


def hash_password(password: str) -> str:
    """Return a bcrypt hash for ``password``."""
    return bcrypt.hashpw(_to_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Return ``True`` if ``password`` matches the stored ``password_hash``."""
    try:
        return bcrypt.checkpw(_to_bytes(password), password_hash.encode("utf-8"))
    except ValueError:
        return False

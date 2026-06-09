"""Startup helpers: create tables and bootstrap the first admin account."""

import logging

from app.config import get_settings
from app.database import Base, SessionLocal, engine

# Importing the models package registers every table on ``Base.metadata``.
from app import models  # noqa: F401  (side-effect import)
from app.models.admin_user import AdminUser
from app.security.passwords import hash_password

logger = logging.getLogger("control_plane.bootstrap")


def init_database() -> None:
    """Create all tables if they do not yet exist.

    For production use Alembic migrations; ``create_all`` is a convenience for dev
    and first boot.
    """
    Base.metadata.create_all(bind=engine)


def bootstrap_admin() -> None:
    """Create the bootstrap admin from settings if no admin exists yet."""
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        return

    with SessionLocal() as db:
        if db.query(AdminUser).count() > 0:
            return
        admin = AdminUser(
            email=settings.bootstrap_admin_email,
            password_hash=hash_password(settings.bootstrap_admin_password),
        )
        db.add(admin)
        db.commit()
        logger.warning(
            "Bootstrapped initial admin %s — change this password immediately.",
            settings.bootstrap_admin_email,
        )

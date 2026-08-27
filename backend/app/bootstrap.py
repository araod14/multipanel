"""Startup helpers: create tables and bootstrap the first admin account."""

import logging

from sqlalchemy import inspect, text

from app.config import get_settings
from app.database import Base, SessionLocal, engine

# Importing the models package registers every table on ``Base.metadata``.
from app import models  # noqa: F401  (side-effect import)
from app.models.admin_user import AdminUser
from app.security.passwords import hash_password

logger = logging.getLogger("control_plane.bootstrap")


# Columns added to existing tables after the first release, as
# ``table -> {column: DDL type + default}``. ``create_all`` only ever CREATEs, so a
# new column never reaches a database that already has the table. Dropping the
# database (the documented dev workaround) is not an option in production, and the
# project does not run Alembic — so additive columns are applied here, explicitly.
# ONLY nullable/defaulted ADD COLUMN belongs here; anything else needs a real
# migration tool.
_ADDITIVE_COLUMNS: dict[str, dict[str, str]] = {
    "bot_instances": {"trading_enabled": "BOOLEAN NOT NULL DEFAULT 0"},
}


def init_database() -> None:
    """Create all tables if they do not yet exist, then apply additive columns."""
    Base.metadata.create_all(bind=engine)
    _apply_additive_columns()


def _apply_additive_columns() -> None:
    """Add any missing column from :data:`_ADDITIVE_COLUMNS`. Safe to re-run."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _ADDITIVE_COLUMNS.items():
            if table not in existing_tables:
                continue  # create_all just made it, with every column already present
            present = {c["name"] for c in inspector.get_columns(table)}
            for column, ddl in columns.items():
                if column in present:
                    continue
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                logger.warning("Added missing column %s.%s", table, column)


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

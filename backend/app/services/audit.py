"""Helper for writing audit-log entries."""

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record(
    db: Session,
    *,
    actor: str,
    action: str,
    target_user_id: int | None = None,
    detail: str | None = None,
) -> AuditLog:
    """Append an audit-log row and flush it.

    :param actor: principal performing the action, e.g. ``"admin:3"``.
    :param action: short verb, e.g. ``"user.create"`` or ``"bot.start"``.
    :param target_user_id: affected user id, if any.
    :param detail: optional free-text context (never include plaintext secrets).
    """
    entry = AuditLog(actor=actor, action=action, target_user_id=target_user_id, detail=detail)
    db.add(entry)
    db.flush()
    return entry

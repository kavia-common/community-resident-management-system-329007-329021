"""
Audit logging service.

Flow: AuditLogFlow
- Provides a single function to record audit log entries.
- Called from route handlers after successful operations.

Contract:
  Input: db session, user_id, action, entity_type, entity_id, details, ip_address
  Output: AuditLog record persisted to database
  Errors: Logs and swallows exceptions to avoid breaking the main flow
  Side effects: INSERT into audit_log table
"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.api.models import AuditLog

logger = logging.getLogger(__name__)


# PUBLIC_INTERFACE
def log_action(
    db: Session,
    user_id: Optional[UUID],
    action: str,
    entity_type: str,
    entity_id: Optional[UUID] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> None:
    """
    Record an audit log entry.

    This function is intentionally fault-tolerant: if the audit insert fails,
    the error is logged but not propagated, so the primary operation is not
    affected.

    Args:
        db: Active database session.
        user_id: UUID of the user performing the action (None for system actions).
        action: Short description of the action (e.g., 'CREATE', 'UPDATE', 'DELETE').
        entity_type: The entity type being acted upon (e.g., 'resident', 'announcement').
        entity_id: UUID of the entity being acted upon.
        details: Optional JSON-serializable dict with additional context.
        ip_address: Client IP address.
    """
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address,
        )
        db.add(entry)
        db.commit()
        logger.info(
            "Audit: user=%s action=%s entity_type=%s entity_id=%s",
            user_id, action, entity_type, entity_id,
        )
    except Exception as exc:
        logger.error("Failed to write audit log: %s", exc)
        db.rollback()

"""
Audit log retrieval routes.

Flow: AuditLogRetrievalFlow
- GET /api/audit-logs — list audit log entries with pagination and filtering

Contract:
  Input: Query params for entity_type, user_id, action, page, page_size
  Output: AuditLogListResponse (paginated)
  Errors: 403 if not admin
"""

import logging
import math
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.auth import require_admin
from src.api.database import get_db
from src.api.models import AuditLog, User
from src.api.schemas import AuditLogListResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit-logs", tags=["Audit Logs"])


# PUBLIC_INTERFACE
@router.get(
    "",
    response_model=AuditLogListResponse,
    summary="List audit logs",
    description="Get paginated audit log entries with optional filtering. Admin only.",
)
def list_audit_logs(
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    List audit log entries with pagination and optional filters.

    Only accessible to admin users. Returns entries in reverse chronological order.
    """
    query = db.query(AuditLog)

    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)

    total = query.count()
    pages = math.ceil(total / page_size) if total > 0 else 1

    items = (
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return AuditLogListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )

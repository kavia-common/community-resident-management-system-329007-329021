"""
Announcement management routes.

Flow: AnnouncementCRUDFlow
- GET /api/announcements — list published announcements (all users)
- POST /api/announcements — create (admin)
- GET /api/announcements/{id} — get single
- PUT /api/announcements/{id} — update (admin)
- DELETE /api/announcements/{id} — delete (admin)

Contract:
  Input: AnnouncementCreate/AnnouncementUpdate for mutations
  Output: AnnouncementResponse
  Errors: 404 not found; 403 forbidden
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.api.auth import get_current_user, require_admin
from src.api.database import get_db
from src.api.models import Announcement, User
from src.api.schemas import (
    AnnouncementCreate,
    AnnouncementUpdate,
    AnnouncementResponse,
)
from src.api.audit_service import log_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/announcements", tags=["Announcements"])


# PUBLIC_INTERFACE
@router.get(
    "",
    response_model=list[AnnouncementResponse],
    summary="List announcements",
    description="Get all published announcements. Optionally include unpublished (admin only).",
)
def list_announcements(
    include_unpublished: bool = Query(False, description="Include unpublished announcements (admin)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List announcements, optionally including unpublished ones for admins."""
    query = db.query(Announcement)

    if not include_unpublished or current_user.role != "admin":
        query = query.filter(Announcement.is_published.is_(True))

    return query.order_by(Announcement.created_at.desc()).all()


# PUBLIC_INTERFACE
@router.post(
    "",
    response_model=AnnouncementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create announcement",
    description="Create a new community announcement. Admin only.",
)
def create_announcement(
    data: AnnouncementCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a new announcement (admin only)."""
    logger.info("Creating announcement: %s", data.title)

    # Validate priority
    valid_priorities = {"low", "normal", "high", "urgent"}
    if data.priority not in valid_priorities:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Priority must be one of: {', '.join(valid_priorities)}",
        )

    announcement = Announcement(
        title=data.title,
        content=data.content,
        priority=data.priority,
        author_id=current_user.id,
        is_published=data.is_published,
        published_at=datetime.now(timezone.utc) if data.is_published else None,
        expires_at=data.expires_at,
    )
    db.add(announcement)
    db.commit()
    db.refresh(announcement)

    log_action(
        db=db,
        user_id=current_user.id,
        action="CREATE",
        entity_type="announcement",
        entity_id=announcement.id,
        details={"title": announcement.title, "priority": announcement.priority},
        ip_address=request.client.host if request.client else None,
    )

    return announcement


# PUBLIC_INTERFACE
@router.get(
    "/{announcement_id}",
    response_model=AnnouncementResponse,
    summary="Get announcement",
    description="Get a single announcement by ID.",
)
def get_announcement(
    announcement_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single announcement by ID."""
    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return announcement


# PUBLIC_INTERFACE
@router.put(
    "/{announcement_id}",
    response_model=AnnouncementResponse,
    summary="Update announcement",
    description="Update an existing announcement. Admin only.",
)
def update_announcement(
    announcement_id: str,
    data: AnnouncementUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update an existing announcement (admin only)."""
    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    update_fields = data.model_dump(exclude_unset=True)

    # If publishing for the first time, set published_at
    if "is_published" in update_fields and update_fields["is_published"] and not announcement.published_at:
        announcement.published_at = datetime.now(timezone.utc)

    for field, value in update_fields.items():
        setattr(announcement, field, value)

    db.commit()
    db.refresh(announcement)

    log_action(
        db=db,
        user_id=current_user.id,
        action="UPDATE",
        entity_type="announcement",
        entity_id=announcement.id,
        details={"updated_fields": list(update_fields.keys())},
        ip_address=request.client.host if request.client else None,
    )

    return announcement


# PUBLIC_INTERFACE
@router.delete(
    "/{announcement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete announcement",
    description="Delete an announcement. Admin only.",
)
def delete_announcement(
    announcement_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete an announcement (admin only)."""
    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    log_action(
        db=db,
        user_id=current_user.id,
        action="DELETE",
        entity_type="announcement",
        entity_id=announcement.id,
        details={"title": announcement.title},
        ip_address=request.client.host if request.client else None,
    )

    db.delete(announcement)
    db.commit()

"""
Emergency contact management routes.

Flow: EmergencyContactCRUDFlow
- GET /api/emergency-contacts — list all (admin) or own contacts
- POST /api/emergency-contacts — create contact (admin)
- GET /api/emergency-contacts/{id} — get single contact
- PUT /api/emergency-contacts/{id} — update contact (admin)
- DELETE /api/emergency-contacts/{id} — delete contact (admin)
- GET /api/emergency-contacts/resident/{resident_id} — contacts for a resident

Contract:
  Input: EmergencyContactCreate/EmergencyContactUpdate for mutations
  Output: EmergencyContactResponse
  Errors: 404 not found; 403 forbidden
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.api.auth import get_current_user, require_admin
from src.api.database import get_db
from src.api.models import EmergencyContact, Resident, User
from src.api.schemas import (
    EmergencyContactCreate,
    EmergencyContactUpdate,
    EmergencyContactResponse,
)
from src.api.audit_service import log_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/emergency-contacts", tags=["Emergency Contacts"])


# PUBLIC_INTERFACE
@router.get(
    "/resident/{resident_id}",
    response_model=list[EmergencyContactResponse],
    summary="Get contacts for a resident",
    description="Get all emergency contacts associated with a specific resident.",
)
def get_contacts_for_resident(
    resident_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all emergency contacts for a specific resident.

    Accessible to all authenticated users.
    """
    # Verify resident exists
    resident = db.query(Resident).filter(Resident.id == resident_id).first()
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")

    contacts = (
        db.query(EmergencyContact)
        .filter(EmergencyContact.resident_id == resident_id)
        .order_by(EmergencyContact.is_primary.desc(), EmergencyContact.contact_name)
        .all()
    )
    return contacts


# PUBLIC_INTERFACE
@router.get(
    "",
    response_model=list[EmergencyContactResponse],
    summary="List all emergency contacts",
    description="Get all emergency contacts in the system. Admin only.",
)
def list_emergency_contacts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all emergency contacts (admin only)."""
    return (
        db.query(EmergencyContact)
        .order_by(EmergencyContact.created_at.desc())
        .all()
    )


# PUBLIC_INTERFACE
@router.post(
    "",
    response_model=EmergencyContactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create emergency contact",
    description="Add a new emergency contact for a resident. Admin only.",
)
def create_emergency_contact(
    data: EmergencyContactCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a new emergency contact for a resident (admin only)."""
    logger.info("Creating emergency contact for resident %s", data.resident_id)

    # Verify resident exists
    resident = db.query(Resident).filter(Resident.id == data.resident_id).first()
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")

    contact = EmergencyContact(**data.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)

    log_action(
        db=db,
        user_id=current_user.id,
        action="CREATE",
        entity_type="emergency_contact",
        entity_id=contact.id,
        details={
            "resident_id": str(data.resident_id),
            "contact_name": contact.contact_name,
        },
        ip_address=request.client.host if request.client else None,
    )

    return contact


# PUBLIC_INTERFACE
@router.get(
    "/{contact_id}",
    response_model=EmergencyContactResponse,
    summary="Get emergency contact",
    description="Get a single emergency contact by ID.",
)
def get_emergency_contact(
    contact_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single emergency contact by ID."""
    contact = db.query(EmergencyContact).filter(EmergencyContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Emergency contact not found")
    return contact


# PUBLIC_INTERFACE
@router.put(
    "/{contact_id}",
    response_model=EmergencyContactResponse,
    summary="Update emergency contact",
    description="Update an existing emergency contact. Admin only.",
)
def update_emergency_contact(
    contact_id: str,
    data: EmergencyContactUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update an existing emergency contact (admin only)."""
    contact = db.query(EmergencyContact).filter(EmergencyContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Emergency contact not found")

    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(contact, field, value)

    db.commit()
    db.refresh(contact)

    log_action(
        db=db,
        user_id=current_user.id,
        action="UPDATE",
        entity_type="emergency_contact",
        entity_id=contact.id,
        details={"updated_fields": list(update_fields.keys())},
        ip_address=request.client.host if request.client else None,
    )

    return contact


# PUBLIC_INTERFACE
@router.delete(
    "/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete emergency contact",
    description="Delete an emergency contact. Admin only.",
)
def delete_emergency_contact(
    contact_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete an emergency contact (admin only)."""
    contact = db.query(EmergencyContact).filter(EmergencyContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Emergency contact not found")

    log_action(
        db=db,
        user_id=current_user.id,
        action="DELETE",
        entity_type="emergency_contact",
        entity_id=contact.id,
        details={"contact_name": contact.contact_name},
        ip_address=request.client.host if request.client else None,
    )

    db.delete(contact)
    db.commit()

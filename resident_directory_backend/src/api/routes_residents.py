"""
Resident management routes.

Flow: ResidentCRUDFlow
- GET /api/residents — list with search, filter, pagination
- POST /api/residents — create resident (admin)
- GET /api/residents/{id} — get single resident
- PUT /api/residents/{id} — update resident (admin)
- DELETE /api/residents/{id} — delete resident (admin)
- GET /api/residents/export/csv — export residents to CSV
- POST /api/residents/import/csv — import residents from CSV

Contract:
  Input: ResidentCreate/ResidentUpdate for mutations; query params for search
  Output: ResidentResponse, ResidentListResponse, CSV file
  Errors: 404 not found; 400 bad request; 403 forbidden
"""

import csv
import io
import logging
import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.api.auth import get_current_user, require_admin
from src.api.database import get_db
from src.api.models import Resident, User
from src.api.schemas import (
    ResidentCreate,
    ResidentUpdate,
    ResidentResponse,
    ResidentListResponse,
)
from src.api.audit_service import log_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/residents", tags=["Residents"])


# PUBLIC_INTERFACE
@router.get(
    "/export/csv",
    summary="Export residents to CSV",
    description="Download all active residents as a CSV file. Admin only.",
    responses={200: {"content": {"text/csv": {}}}},
)
def export_residents_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Export all active residents as a CSV file.

    Returns a streaming CSV response with resident profile data.
    """
    logger.info("CSV export requested by user %s", current_user.username)

    residents = db.query(Resident).filter(Resident.is_active.is_(True)).order_by(
        Resident.last_name, Resident.first_name
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "first_name", "last_name", "email", "phone",
        "unit_number", "building", "move_in_date", "move_out_date", "notes",
    ])
    for r in residents:
        writer.writerow([
            r.first_name, r.last_name, r.email or "", r.phone or "",
            r.unit_number, r.building or "",
            r.move_in_date.isoformat() if r.move_in_date else "",
            r.move_out_date.isoformat() if r.move_out_date else "",
            r.notes or "",
        ])

    output.seek(0)

    log_action(
        db=db,
        user_id=current_user.id,
        action="EXPORT_CSV",
        entity_type="resident",
        details={"count": len(residents)},
    )

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=residents.csv"},
    )


# PUBLIC_INTERFACE
@router.post(
    "/import/csv",
    summary="Import residents from CSV",
    description="Upload a CSV file to bulk-import residents. Admin only.",
    status_code=status.HTTP_201_CREATED,
)
def import_residents_csv(
    request: Request,
    file: UploadFile = File(..., description="CSV file with resident data"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Import residents from an uploaded CSV file.

    Expected CSV columns: first_name, last_name, email, phone,
    unit_number, building, move_in_date, move_out_date, notes.

    Returns a summary of imported/skipped/errored rows.
    """
    logger.info("CSV import requested by user %s", current_user.username)

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file",
        )

    content = file.file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))

    imported = 0
    errors = []

    for row_num, row in enumerate(reader, start=2):
        try:
            first_name = row.get("first_name", "").strip()
            last_name = row.get("last_name", "").strip()
            unit_number = row.get("unit_number", "").strip()

            if not first_name or not last_name or not unit_number:
                errors.append({"row": row_num, "error": "Missing required fields"})
                continue

            from datetime import date as date_type

            move_in = None
            move_out = None
            if row.get("move_in_date", "").strip():
                move_in = date_type.fromisoformat(row["move_in_date"].strip())
            if row.get("move_out_date", "").strip():
                move_out = date_type.fromisoformat(row["move_out_date"].strip())

            resident = Resident(
                first_name=first_name,
                last_name=last_name,
                email=row.get("email", "").strip() or None,
                phone=row.get("phone", "").strip() or None,
                unit_number=unit_number,
                building=row.get("building", "").strip() or None,
                move_in_date=move_in,
                move_out_date=move_out,
                notes=row.get("notes", "").strip() or None,
            )
            db.add(resident)
            imported += 1

        except Exception as exc:
            errors.append({"row": row_num, "error": str(exc)})

    db.commit()

    log_action(
        db=db,
        user_id=current_user.id,
        action="IMPORT_CSV",
        entity_type="resident",
        details={"imported": imported, "errors": len(errors)},
        ip_address=request.client.host if request.client else None,
    )

    return {
        "imported": imported,
        "errors": errors,
        "total_rows": imported + len(errors),
    }


# PUBLIC_INTERFACE
@router.get(
    "",
    response_model=ResidentListResponse,
    summary="List residents",
    description="Get a paginated, searchable list of residents. Supports filtering by active status and building.",
)
def list_residents(
    search: Optional[str] = Query(None, description="Search by name, email, phone, or unit"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    building: Optional[str] = Query(None, description="Filter by building"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List residents with search, filtering, and pagination.

    Accessible to all authenticated users.
    """
    query = db.query(Resident)

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Resident.first_name.ilike(search_term),
                Resident.last_name.ilike(search_term),
                Resident.email.ilike(search_term),
                Resident.phone.ilike(search_term),
                Resident.unit_number.ilike(search_term),
                Resident.building.ilike(search_term),
            )
        )

    # Apply active status filter
    if is_active is not None:
        query = query.filter(Resident.is_active == is_active)

    # Apply building filter
    if building:
        query = query.filter(Resident.building.ilike(f"%{building}%"))

    # Get total count
    total = query.count()
    pages = math.ceil(total / page_size) if total > 0 else 1

    # Apply pagination
    residents = (
        query.order_by(Resident.last_name, Resident.first_name)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return ResidentListResponse(
        items=residents,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


# PUBLIC_INTERFACE
@router.post(
    "",
    response_model=ResidentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create resident",
    description="Create a new resident profile. Admin only.",
)
def create_resident(
    resident_data: ResidentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a new resident profile (admin only)."""
    logger.info("Creating resident: %s %s", resident_data.first_name, resident_data.last_name)

    resident = Resident(**resident_data.model_dump())
    db.add(resident)
    db.commit()
    db.refresh(resident)

    log_action(
        db=db,
        user_id=current_user.id,
        action="CREATE",
        entity_type="resident",
        entity_id=resident.id,
        details={"name": f"{resident.first_name} {resident.last_name}", "unit": resident.unit_number},
        ip_address=request.client.host if request.client else None,
    )

    return resident


# PUBLIC_INTERFACE
@router.get(
    "/{resident_id}",
    response_model=ResidentResponse,
    summary="Get resident",
    description="Get a single resident profile by ID.",
)
def get_resident(
    resident_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single resident by ID."""
    resident = db.query(Resident).filter(Resident.id == resident_id).first()
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")
    return resident


# PUBLIC_INTERFACE
@router.put(
    "/{resident_id}",
    response_model=ResidentResponse,
    summary="Update resident",
    description="Update an existing resident profile. Admin only.",
)
def update_resident(
    resident_id: str,
    resident_data: ResidentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update an existing resident profile (admin only)."""
    resident = db.query(Resident).filter(Resident.id == resident_id).first()
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")

    update_fields = resident_data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(resident, field, value)

    db.commit()
    db.refresh(resident)

    log_action(
        db=db,
        user_id=current_user.id,
        action="UPDATE",
        entity_type="resident",
        entity_id=resident.id,
        details={"updated_fields": list(update_fields.keys())},
        ip_address=request.client.host if request.client else None,
    )

    return resident


# PUBLIC_INTERFACE
@router.delete(
    "/{resident_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete resident",
    description="Delete a resident profile. Admin only.",
)
def delete_resident(
    resident_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete a resident profile (admin only)."""
    resident = db.query(Resident).filter(Resident.id == resident_id).first()
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")

    log_action(
        db=db,
        user_id=current_user.id,
        action="DELETE",
        entity_type="resident",
        entity_id=resident.id,
        details={"name": f"{resident.first_name} {resident.last_name}", "unit": resident.unit_number},
        ip_address=request.client.host if request.client else None,
    )

    db.delete(resident)
    db.commit()

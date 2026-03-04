"""
Pydantic schemas for request/response validation and serialization.

Contract:
  - All UUID fields are serialized as strings in JSON responses.
  - Datetime fields are serialized as ISO 8601 strings.
  - Input schemas validate required fields and constraints.
  - Output schemas map directly from ORM model attributes.
"""

from datetime import date, datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr, ConfigDict


# ─── Auth Schemas ────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """Schema for user login request."""
    username: str = Field(..., description="Username for authentication")
    password: str = Field(..., description="User password")


class TokenResponse(BaseModel):
    """Schema for JWT token response."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    user_id: str = Field(..., description="Authenticated user ID")
    username: str = Field(..., description="Authenticated username")
    role: str = Field(..., description="User role (admin or resident)")


class UserCreate(BaseModel):
    """Schema for creating a new user."""
    username: str = Field(..., min_length=3, max_length=100, description="Unique username")
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, max_length=128, description="User password")
    role: str = Field(default="resident", description="User role: admin or resident")


class UserResponse(BaseModel):
    """Schema for user data in responses."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="User UUID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    role: str = Field(..., description="User role")
    is_active: bool = Field(..., description="Whether user account is active")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    email: Optional[EmailStr] = Field(None, description="Updated email")
    role: Optional[str] = Field(None, description="Updated role")
    is_active: Optional[bool] = Field(None, description="Updated active status")


# ─── Resident Schemas ────────────────────────────────────────────────────────

class ResidentCreate(BaseModel):
    """Schema for creating a new resident profile."""
    first_name: str = Field(..., min_length=1, max_length=100, description="First name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Last name")
    email: Optional[str] = Field(None, max_length=255, description="Email address")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number")
    unit_number: str = Field(..., min_length=1, max_length=50, description="Unit/apartment number")
    building: Optional[str] = Field(None, max_length=100, description="Building name")
    photo_url: Optional[str] = Field(None, max_length=500, description="URL to resident photo")
    move_in_date: Optional[date] = Field(None, description="Move-in date")
    move_out_date: Optional[date] = Field(None, description="Move-out date")
    is_active: bool = Field(default=True, description="Whether resident is currently active")
    notes: Optional[str] = Field(None, description="Additional notes")
    user_id: Optional[UUID] = Field(None, description="Associated user account ID")


class ResidentUpdate(BaseModel):
    """Schema for updating a resident profile."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100, description="First name")
    last_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Last name")
    email: Optional[str] = Field(None, max_length=255, description="Email address")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number")
    unit_number: Optional[str] = Field(None, min_length=1, max_length=50, description="Unit number")
    building: Optional[str] = Field(None, max_length=100, description="Building name")
    photo_url: Optional[str] = Field(None, max_length=500, description="Photo URL")
    move_in_date: Optional[date] = Field(None, description="Move-in date")
    move_out_date: Optional[date] = Field(None, description="Move-out date")
    is_active: Optional[bool] = Field(None, description="Active status")
    notes: Optional[str] = Field(None, description="Additional notes")
    user_id: Optional[UUID] = Field(None, description="Associated user account ID")


class ResidentResponse(BaseModel):
    """Schema for resident data in responses."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Resident UUID")
    user_id: Optional[UUID] = Field(None, description="Associated user ID")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    unit_number: str = Field(..., description="Unit/apartment number")
    building: Optional[str] = Field(None, description="Building name")
    photo_url: Optional[str] = Field(None, description="Photo URL")
    move_in_date: Optional[date] = Field(None, description="Move-in date")
    move_out_date: Optional[date] = Field(None, description="Move-out date")
    is_active: bool = Field(..., description="Active status")
    notes: Optional[str] = Field(None, description="Notes")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class ResidentListResponse(BaseModel):
    """Paginated list of residents."""
    items: List[ResidentResponse] = Field(..., description="List of residents")
    total: int = Field(..., description="Total number of matching residents")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")


# ─── Announcement Schemas ────────────────────────────────────────────────────

class AnnouncementCreate(BaseModel):
    """Schema for creating an announcement."""
    title: str = Field(..., min_length=1, max_length=255, description="Announcement title")
    content: str = Field(..., min_length=1, description="Announcement body")
    priority: str = Field(default="normal", description="Priority: low, normal, high, urgent")
    is_published: bool = Field(default=True, description="Publish immediately")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")


class AnnouncementUpdate(BaseModel):
    """Schema for updating an announcement."""
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Title")
    content: Optional[str] = Field(None, min_length=1, description="Content")
    priority: Optional[str] = Field(None, description="Priority level")
    is_published: Optional[bool] = Field(None, description="Published status")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")


class AnnouncementResponse(BaseModel):
    """Schema for announcement data in responses."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Announcement UUID")
    title: str = Field(..., description="Title")
    content: str = Field(..., description="Content")
    priority: str = Field(..., description="Priority level")
    author_id: Optional[UUID] = Field(None, description="Author user ID")
    is_published: bool = Field(..., description="Published status")
    published_at: Optional[datetime] = Field(None, description="Publication timestamp")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# ─── Emergency Contact Schemas ───────────────────────────────────────────────

class EmergencyContactCreate(BaseModel):
    """Schema for creating an emergency contact."""
    resident_id: UUID = Field(..., description="Associated resident ID")
    contact_name: str = Field(..., min_length=1, max_length=200, description="Contact name")
    relationship: Optional[str] = Field(None, max_length=100, description="Relationship to resident")
    phone: str = Field(..., min_length=1, max_length=50, description="Phone number")
    email: Optional[str] = Field(None, max_length=255, description="Email address")
    is_primary: bool = Field(default=False, description="Whether this is the primary contact")


class EmergencyContactUpdate(BaseModel):
    """Schema for updating an emergency contact."""
    contact_name: Optional[str] = Field(None, min_length=1, max_length=200, description="Contact name")
    relationship: Optional[str] = Field(None, max_length=100, description="Relationship")
    phone: Optional[str] = Field(None, min_length=1, max_length=50, description="Phone number")
    email: Optional[str] = Field(None, max_length=255, description="Email")
    is_primary: Optional[bool] = Field(None, description="Primary contact flag")


class EmergencyContactResponse(BaseModel):
    """Schema for emergency contact data in responses."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Contact UUID")
    resident_id: UUID = Field(..., description="Associated resident ID")
    contact_name: str = Field(..., description="Contact name")
    relationship: Optional[str] = Field(None, description="Relationship")
    phone: str = Field(..., description="Phone number")
    email: Optional[str] = Field(None, description="Email")
    is_primary: bool = Field(..., description="Primary contact flag")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# ─── Audit Log Schemas ───────────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    """Schema for audit log entries in responses."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Audit log entry UUID")
    user_id: Optional[UUID] = Field(None, description="User who performed the action")
    action: str = Field(..., description="Action performed")
    entity_type: str = Field(..., description="Entity type affected")
    entity_id: Optional[UUID] = Field(None, description="Entity ID affected")
    details: Optional[dict] = Field(None, description="Additional details as JSON")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    created_at: datetime = Field(..., description="Timestamp of the action")


class AuditLogListResponse(BaseModel):
    """Paginated list of audit log entries."""
    items: List[AuditLogResponse] = Field(..., description="Audit log entries")
    total: int = Field(..., description="Total matching entries")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total pages")

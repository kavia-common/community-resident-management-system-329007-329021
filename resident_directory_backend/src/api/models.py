"""
SQLAlchemy ORM models for the resident directory database.

Maps to the existing PostgreSQL schema (tables created by the database container).
All tables use UUID primary keys via the uuid-ossp extension.

Invariants:
  - user.role must be 'admin' or 'resident'
  - announcement.priority must be 'low', 'normal', 'high', or 'urgent'
  - All timestamps are timezone-aware (TIMESTAMP WITH TIME ZONE)
"""

import uuid

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Text,
    Date,
    ForeignKey,
    DateTime,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship as orm_relationship
from sqlalchemy.sql import func

from src.api.database import Base


class User(Base):
    """User authentication and role model."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="resident")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    resident = orm_relationship("Resident", back_populates="user", uselist=False)
    announcements = orm_relationship("Announcement", back_populates="author")
    audit_logs = orm_relationship("AuditLog", back_populates="user")


class Resident(Base):
    """Resident profile model."""

    __tablename__ = "residents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    unit_number = Column(String(50), nullable=False)
    building = Column(String(100), nullable=True)
    photo_url = Column(String(500), nullable=True)
    move_in_date = Column(Date, nullable=True)
    move_out_date = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = orm_relationship("User", back_populates="resident")
    emergency_contacts = orm_relationship(
        "EmergencyContact", back_populates="resident", cascade="all, delete-orphan"
    )


class Announcement(Base):
    """Community announcement model."""

    __tablename__ = "announcements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    priority = Column(String(20), nullable=False, default="normal")
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_published = Column(Boolean, nullable=False, default=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    author = orm_relationship("User", back_populates="announcements")


class EmergencyContact(Base):
    """Emergency contact for a resident."""

    __tablename__ = "emergency_contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("residents.id", ondelete="CASCADE"),
        nullable=False,
    )
    contact_name = Column(String(200), nullable=False)
    relationship = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=False)
    email = Column(String(255), nullable=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships — using orm_relationship to avoid shadowing by the 'relationship' column
    resident = orm_relationship("Resident", back_populates="emergency_contacts")


class AuditLog(Base):
    """Audit log entry tracking user actions."""

    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    details = Column(JSONB, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = orm_relationship("User", back_populates="audit_logs")

"""
Huddle (Tenant) Model for Multi-Tenancy Support

This module provides tenant isolation for the AlumniHuddle platform.
Each huddle represents a university team/group (e.g., hoosiers-football).

Huddles are identified by slug (subdomain) and have isolated data access.
Uses the existing 'huddles' table from AlumniHuddle's main database.
"""

import logging
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, Column, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from open_webui.internal.db import Base, get_db_context

log = logging.getLogger(__name__)


####################
# Huddle DB Schema (maps to existing 'huddles' table)
####################


class Huddle(Base):
    """Maps to the existing 'huddles' table in Supabase."""
    __tablename__ = "huddles"

    id = Column(UUID(as_uuid=True), primary_key=True)
    name = Column(Text, nullable=False)  # Display name: "Indiana Football"
    slug = Column(Text, unique=True, nullable=False)  # URL subdomain: "hoosiers-football"
    logo_url = Column(Text, nullable=True)
    primary_color = Column(Text, nullable=True)
    secondary_color = Column(Text, nullable=True)
    require_approval = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    cover_photo_url = Column(Text, nullable=True)
    admin_email = Column(Text, nullable=True)
    description = Column(Text, nullable=True)


####################
# Pydantic Models
####################


class HuddleModel(BaseModel):
    """Pydantic model for Huddle data."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    logo_url: Optional[str] = None
    cover_photo_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    require_approval: bool = False
    admin_email: Optional[str] = None
    description: Optional[str] = None

    @classmethod
    def from_orm_with_str_id(cls, huddle: Huddle) -> "HuddleModel":
        """Convert ORM object to Pydantic model with string ID."""
        return cls(
            id=str(huddle.id),
            name=huddle.name,
            slug=huddle.slug,
            logo_url=huddle.logo_url,
            cover_photo_url=huddle.cover_photo_url,
            primary_color=huddle.primary_color,
            secondary_color=huddle.secondary_color,
            require_approval=huddle.require_approval or False,
            admin_email=huddle.admin_email,
            description=huddle.description,
        )


class HuddleResponse(BaseModel):
    """Response model for API endpoints."""
    id: str
    name: str
    slug: str
    logo_url: Optional[str] = None
    is_active: bool = True


# Backward compatibility aliases
TenantModel = HuddleModel
TenantResponse = HuddleResponse


####################
# Huddle Table Operations
####################


class HuddleTable:
    """
    Database operations for Huddle (tenant) management.

    Uses the existing 'huddles' table from AlumniHuddle.
    """

    def get_huddle_by_id(
        self,
        huddle_id: str,
        db: Optional[Session] = None,
    ) -> Optional[HuddleModel]:
        """Get huddle by ID."""
        with get_db_context(db) as db:
            huddle = db.query(Huddle).filter_by(id=huddle_id).first()
            if huddle and huddle.deleted_at is None:
                return HuddleModel.from_orm_with_str_id(huddle)
            return None

    def get_huddle_by_slug(
        self,
        slug: str,
        db: Optional[Session] = None,
    ) -> Optional[HuddleModel]:
        """Get huddle by slug (subdomain) - used for routing."""
        with get_db_context(db) as db:
            huddle = db.query(Huddle).filter_by(slug=slug.lower()).first()
            if huddle and huddle.deleted_at is None:
                return HuddleModel.from_orm_with_str_id(huddle)
            return None

    def get_all_huddles(
        self,
        include_deleted: bool = False,
        skip: int = 0,
        limit: int = 50,
        db: Optional[Session] = None,
    ) -> list[HuddleModel]:
        """Get all huddles with optional filtering."""
        with get_db_context(db) as db:
            query = db.query(Huddle)

            if not include_deleted:
                query = query.filter(Huddle.deleted_at.is_(None))

            query = query.order_by(Huddle.name.asc())

            if skip:
                query = query.offset(skip)
            if limit:
                query = query.limit(limit)

            huddles = query.all()
            return [HuddleModel.from_orm_with_str_id(h) for h in huddles]

    # Backward compatibility methods (alias to new names)
    def get_tenant_by_id(self, tenant_id: str, db: Optional[Session] = None) -> Optional[HuddleModel]:
        return self.get_huddle_by_id(tenant_id, db)

    def get_tenant_by_subdomain(self, subdomain: str, db: Optional[Session] = None) -> Optional[HuddleModel]:
        return self.get_huddle_by_slug(subdomain, db)

    def get_all_tenants(self, include_inactive: bool = False, skip: int = 0, limit: int = 50, db: Optional[Session] = None) -> list[HuddleModel]:
        return self.get_all_huddles(include_deleted=include_inactive, skip=skip, limit=limit, db=db)


# Singleton instances for global access
Huddles = HuddleTable()
Tenants = HuddleTable()  # Backward compatibility

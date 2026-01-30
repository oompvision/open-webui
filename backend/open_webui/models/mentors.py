"""
Mentor Profile Model for AlumniHuddle

This module provides access to mentor profiles from the AlumniHuddle 'profiles' table.
Mentors are users with mentorship_status = 'Willing to mentor'.
"""

import logging
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, Text, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from open_webui.internal.db import Base, get_db_context

log = logging.getLogger(__name__)


####################
# Profile DB Schema (maps to existing 'profiles' table)
####################


class Profile(Base):
    """Maps to the existing 'profiles' table in Supabase."""
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True)
    huddle_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    full_name = Column(Text, nullable=False)
    class_year = Column(Integer, nullable=False)
    work_email = Column(Text, nullable=True)
    personal_email = Column(Text, nullable=False)
    phone_number = Column(Text, nullable=True)
    show_phone = Column(Boolean, default=False)
    show_email = Column(Boolean, default=False)
    metro_area = Column(Text, nullable=False)
    linkedin_url = Column(Text, nullable=True)
    current_company = Column(Text, nullable=True)
    title = Column(Text, nullable=True)
    prior_roles = Column(Text, nullable=True)
    industry = Column(Text, nullable=True)
    skills_experience = Column(Text, nullable=True)
    mentorship_status = Column(Text, nullable=False)
    resume_url = Column(Text, nullable=True)
    photo_url = Column(Text, nullable=True)
    instagram = Column(Text, nullable=True)
    twitter = Column(Text, nullable=True)
    personal_website = Column(Text, nullable=True)
    email_digest_opt_in = Column(Boolean, default=True)
    status = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    admin_notes = Column(Text, nullable=True)


####################
# Pydantic Models
####################


class MentorProfileModel(BaseModel):
    """Pydantic model for mentor profile data."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    huddle_id: str
    full_name: str
    class_year: int
    metro_area: str
    current_company: Optional[str] = None
    title: Optional[str] = None
    prior_roles: Optional[str] = None
    industry: Optional[str] = None
    skills_experience: Optional[str] = None
    linkedin_url: Optional[str] = None
    photo_url: Optional[str] = None

    @classmethod
    def from_orm_with_str_id(cls, profile: Profile) -> "MentorProfileModel":
        """Convert ORM object to Pydantic model with string IDs."""
        return cls(
            id=str(profile.id),
            huddle_id=str(profile.huddle_id),
            full_name=profile.full_name,
            class_year=profile.class_year,
            metro_area=profile.metro_area,
            current_company=profile.current_company,
            title=profile.title,
            prior_roles=profile.prior_roles,
            industry=profile.industry,
            skills_experience=profile.skills_experience,
            linkedin_url=profile.linkedin_url,
            photo_url=profile.photo_url,
        )

    def to_rag_document(self) -> str:
        """
        Convert mentor profile to a text document for RAG indexing.
        This creates a searchable text representation of the mentor.
        """
        parts = [
            f"Name: {self.full_name}",
            f"Class Year: {self.class_year}",
            f"Location: {self.metro_area}",
        ]

        if self.title and self.current_company:
            parts.append(f"Current Role: {self.title} at {self.current_company}")
        elif self.title:
            parts.append(f"Current Role: {self.title}")
        elif self.current_company:
            parts.append(f"Current Company: {self.current_company}")

        if self.industry:
            parts.append(f"Industry: {self.industry}")

        if self.skills_experience:
            parts.append(f"Skills & Experience: {self.skills_experience}")

        if self.prior_roles:
            parts.append(f"Prior Roles: {self.prior_roles}")

        return "\n".join(parts)


class MentorSearchResult(BaseModel):
    """Search result for mentor queries."""
    mentor: MentorProfileModel
    relevance_score: float


####################
# Mentor Table Operations
####################


class MentorTable:
    """
    Database operations for accessing mentor profiles.
    """

    MENTOR_STATUS = "Willing to mentor"

    def get_mentors_by_huddle(
        self,
        huddle_id: str,
        skip: int = 0,
        limit: int = 100,
        db: Optional[Session] = None,
    ) -> List[MentorProfileModel]:
        """Get all mentors for a specific huddle."""
        with get_db_context(db) as db:
            query = db.query(Profile).filter(
                Profile.huddle_id == huddle_id,
                Profile.mentorship_status == self.MENTOR_STATUS,
                Profile.deleted_at.is_(None),
            )

            query = query.order_by(Profile.full_name.asc())

            if skip:
                query = query.offset(skip)
            if limit:
                query = query.limit(limit)

            profiles = query.all()
            return [MentorProfileModel.from_orm_with_str_id(p) for p in profiles]

    def get_mentor_by_id(
        self,
        mentor_id: str,
        db: Optional[Session] = None,
    ) -> Optional[MentorProfileModel]:
        """Get a specific mentor by ID."""
        with get_db_context(db) as db:
            profile = db.query(Profile).filter(
                Profile.id == mentor_id,
                Profile.mentorship_status == self.MENTOR_STATUS,
                Profile.deleted_at.is_(None),
            ).first()

            if profile:
                return MentorProfileModel.from_orm_with_str_id(profile)
            return None

    def get_mentor_count_by_huddle(
        self,
        huddle_id: str,
        db: Optional[Session] = None,
    ) -> int:
        """Get count of mentors for a huddle."""
        with get_db_context(db) as db:
            return db.query(Profile).filter(
                Profile.huddle_id == huddle_id,
                Profile.mentorship_status == self.MENTOR_STATUS,
                Profile.deleted_at.is_(None),
            ).count()

    def get_all_huddle_ids_with_mentors(
        self,
        db: Optional[Session] = None,
    ) -> List[str]:
        """Get all huddle IDs that have at least one mentor."""
        with get_db_context(db) as db:
            results = db.query(Profile.huddle_id).filter(
                Profile.mentorship_status == self.MENTOR_STATUS,
                Profile.deleted_at.is_(None),
            ).distinct().all()

            return [str(r[0]) for r in results]


# Singleton instance for global access
Mentors = MentorTable()

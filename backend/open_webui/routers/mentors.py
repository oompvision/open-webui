"""
Mentor API Router for AlumniHuddle

Provides API endpoints for:
- Searching mentors within a huddle (using RAG)
- Indexing mentor profiles
- Getting mentor statistics
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from open_webui.models.mentors import Mentors, MentorProfileModel
from open_webui.models.tenants import Huddles
from open_webui.services.mentor_rag import MentorRAGService, get_mentor_collection_name
from open_webui.middleware.tenant import get_current_huddle, require_huddle
from open_webui.utils.auth import get_admin_user, get_verified_user

log = logging.getLogger(__name__)

router = APIRouter()


############################
# Request/Response Models
############################


class MentorSearchRequest(BaseModel):
    query: str
    limit: int = 5


class MentorSearchResult(BaseModel):
    mentor: MentorProfileModel
    relevance_score: float
    document_text: Optional[str] = None


class MentorSearchResponse(BaseModel):
    results: List[MentorSearchResult]
    query: str
    huddle_id: str
    huddle_name: str


class MentorIndexResponse(BaseModel):
    indexed: int
    failed: int
    total: int
    huddle_id: str
    huddle_name: str


class MentorStatsResponse(BaseModel):
    huddle_id: str
    huddle_name: str
    total_mentors: int
    indexed_mentors: int
    collection_exists: bool


############################
# Mentor Search Endpoints
############################


@router.post("/search", response_model=MentorSearchResponse)
async def search_mentors(
    request: Request,
    search_request: MentorSearchRequest,
    user=Depends(get_verified_user),
):
    """
    Search for mentors within the current huddle.

    The huddle is determined from the subdomain or X-Tenant-Subdomain header.
    Returns mentors matching the search query, ranked by relevance.
    """
    huddle = get_current_huddle(request)

    if not huddle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No huddle context found. Access this from a huddle subdomain.",
        )

    # Get embedding function from app state
    embedding_function = getattr(request.app.state, "EMBEDDING_FUNCTION", None)
    if not embedding_function:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding service not available",
        )

    service = MentorRAGService(embedding_function)
    results = await service.search_mentors(
        huddle_id=huddle.id,
        query=search_request.query,
        limit=search_request.limit,
    )

    return MentorSearchResponse(
        results=[
            MentorSearchResult(
                mentor=MentorProfileModel(**r["mentor"]),
                relevance_score=r["relevance_score"],
                document_text=r.get("document_text"),
            )
            for r in results
        ],
        query=search_request.query,
        huddle_id=huddle.id,
        huddle_name=huddle.name,
    )


@router.get("/", response_model=List[MentorProfileModel])
async def list_mentors(
    request: Request,
    skip: int = 0,
    limit: int = 50,
    user=Depends(get_verified_user),
):
    """
    List all mentors in the current huddle.

    Returns basic mentor profiles without RAG search.
    """
    huddle = get_current_huddle(request)

    if not huddle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No huddle context found. Access this from a huddle subdomain.",
        )

    mentors = Mentors.get_mentors_by_huddle(
        huddle_id=huddle.id,
        skip=skip,
        limit=limit,
    )

    return mentors


@router.get("/{mentor_id}", response_model=MentorProfileModel)
async def get_mentor(
    request: Request,
    mentor_id: str,
    user=Depends(get_verified_user),
):
    """
    Get a specific mentor's profile.
    """
    huddle = get_current_huddle(request)

    mentor = Mentors.get_mentor_by_id(mentor_id)

    if not mentor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mentor not found",
        )

    # Verify mentor belongs to current huddle (if huddle context exists)
    if huddle and mentor.huddle_id != huddle.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mentor not accessible from this huddle",
        )

    return mentor


############################
# Admin Endpoints (Indexing)
############################


@router.post("/index", response_model=MentorIndexResponse)
async def index_huddle_mentors(
    request: Request,
    user=Depends(get_admin_user),
):
    """
    Index all mentors for the current huddle into the RAG system.

    Admin only. This creates/updates the vector embeddings for mentor search.
    """
    huddle = get_current_huddle(request)

    if not huddle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No huddle context found. Access this from a huddle subdomain.",
        )

    embedding_function = getattr(request.app.state, "EMBEDDING_FUNCTION", None)
    if not embedding_function:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding service not available",
        )

    service = MentorRAGService(embedding_function)
    results = await service.index_all_mentors_for_huddle(huddle.id)

    return MentorIndexResponse(
        indexed=results["indexed"],
        failed=results["failed"],
        total=results["total"],
        huddle_id=huddle.id,
        huddle_name=huddle.name,
    )


@router.post("/index/all", response_model=dict)
async def index_all_mentors(
    request: Request,
    user=Depends(get_admin_user),
):
    """
    Index all mentors across all huddles.

    Master admin only. Useful for initial setup or rebuilding the index.
    """
    embedding_function = getattr(request.app.state, "EMBEDDING_FUNCTION", None)
    if not embedding_function:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding service not available",
        )

    service = MentorRAGService(embedding_function)
    results = await service.index_all_mentors()

    return {"status": "ok", "results": results}


@router.get("/stats", response_model=MentorStatsResponse)
async def get_mentor_stats(
    request: Request,
    user=Depends(get_verified_user),
):
    """
    Get mentor statistics for the current huddle.

    Shows total mentors and how many are indexed in the RAG system.
    """
    huddle = get_current_huddle(request)

    if not huddle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No huddle context found.",
        )

    total_mentors = Mentors.get_mentor_count_by_huddle(huddle.id)

    service = MentorRAGService()
    collection_stats = service.get_collection_stats(huddle.id)

    return MentorStatsResponse(
        huddle_id=huddle.id,
        huddle_name=huddle.name,
        total_mentors=total_mentors,
        indexed_mentors=collection_stats.get("count", 0),
        collection_exists=collection_stats.get("exists", False),
    )

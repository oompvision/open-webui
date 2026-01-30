"""
Huddle (Tenant) API Router for AlumniHuddle

Provides API endpoints for huddle context and listing.
Huddles are managed via the main AlumniHuddle app, not here.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel

from open_webui.models.tenants import (
    Huddles,
    HuddleModel,
    HuddleResponse,
)
from open_webui.utils.auth import get_admin_user, get_current_user

log = logging.getLogger(__name__)

router = APIRouter()


############################
# Dynamic CSS for Branding
############################


@router.get("/branding.css")
async def get_huddle_branding_css(request: Request):
    """
    Generate dynamic CSS based on the current huddle's branding colors.

    This CSS applies huddle-specific theme colors to the UI.
    Include this stylesheet to customize the appearance for each huddle.
    """
    huddle = getattr(request.state, "tenant", None) or getattr(request.state, "huddle", None)

    if not huddle or not huddle.primary_color:
        # Return empty CSS if no huddle or no primary color
        return Response(content="/* No huddle branding */", media_type="text/css")

    primary = huddle.primary_color or "#3b82f6"
    secondary = huddle.secondary_color or "#000000"

    css = f"""
/* AlumniHuddle Dynamic Branding CSS for {huddle.name} */
/* Minimal branding - keeps header styled but uses black text throughout */
:root {{
    --huddle-primary: {primary};
    --huddle-secondary: {secondary};
}}

/* Primary action buttons only */
button.bg-black {{
    background-color: {primary} !important;
}}

/* Send button / primary CTA buttons */
button[type="submit"].bg-black,
.chat-input button.bg-black {{
    background-color: {primary} !important;
}}
"""

    return Response(content=css, media_type="text/css")


############################
# Huddle Context Endpoints
############################


class HuddleContextResponse(BaseModel):
    huddle: Optional[HuddleResponse] = None
    source: str  # 'subdomain', 'header', or 'none'


class HuddleBrandingResponse(BaseModel):
    """Branding information for the current huddle."""
    id: str
    name: str
    slug: str
    logo_url: Optional[str] = None
    cover_photo_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    description: Optional[str] = None


# Backward compatibility alias
TenantContextResponse = HuddleContextResponse


@router.get("/context", response_model=HuddleContextResponse)
async def get_huddle_context(request: Request):
    """
    Get the current huddle context from the request.

    This endpoint is useful for:
    - Debugging huddle detection
    - Frontend to know which huddle is active
    - Testing with X-Tenant-Subdomain header (uses slug)
    """
    from open_webui.middleware.tenant import extract_subdomain, ENABLE_MULTI_TENANCY

    if not ENABLE_MULTI_TENANCY:
        return HuddleContextResponse(huddle=None, source="disabled")

    # Check for huddle in request state (set by middleware)
    huddle = getattr(request.state, "tenant", None)
    if huddle:
        return HuddleContextResponse(
            huddle=HuddleResponse(
                id=huddle.id,
                name=huddle.name,
                slug=huddle.slug,
                logo_url=huddle.logo_url,
                is_active=True,
            ),
            source="middleware",
        )

    # Try to extract from host
    host = request.headers.get("host", "")
    subdomain = extract_subdomain(host)
    source = "subdomain"

    # Fall back to header for local dev
    if not subdomain:
        subdomain = request.headers.get("x-tenant-subdomain")
        source = "header" if subdomain else "none"

    if subdomain:
        huddle_model = Huddles.get_huddle_by_slug(subdomain)
        if huddle_model:
            return HuddleContextResponse(
                huddle=HuddleResponse(
                    id=huddle_model.id,
                    name=huddle_model.name,
                    slug=huddle_model.slug,
                    logo_url=huddle_model.logo_url,
                    is_active=True,
                ),
                source=source,
            )

    return HuddleContextResponse(huddle=None, source=source)


@router.get("/branding", response_model=Optional[HuddleBrandingResponse])
async def get_huddle_branding(request: Request):
    """
    Get branding information for the current huddle.

    Returns logo, cover photo, colors, etc. for UI customization.
    This endpoint is public (no auth required) so the frontend can style itself.
    """
    # Check for huddle in request state (set by middleware)
    huddle = getattr(request.state, "tenant", None) or getattr(request.state, "huddle", None)

    if not huddle:
        return None

    return HuddleBrandingResponse(
        id=huddle.id,
        name=huddle.name,
        slug=huddle.slug,
        logo_url=huddle.logo_url,
        cover_photo_url=huddle.cover_photo_url,
        primary_color=huddle.primary_color,
        secondary_color=huddle.secondary_color,
        description=huddle.description,
    )


############################
# Huddle Listing Endpoints
############################


@router.get("/", response_model=list[HuddleResponse])
async def list_huddles(
    skip: int = 0,
    limit: int = 50,
    user=Depends(get_admin_user),
):
    """List all huddles (admin only)."""
    huddles = Huddles.get_all_huddles(
        skip=skip,
        limit=limit,
    )
    return [
        HuddleResponse(
            id=h.id,
            name=h.name,
            slug=h.slug,
            logo_url=h.logo_url,
            is_active=True,
        )
        for h in huddles
    ]


@router.get("/{huddle_id}", response_model=HuddleModel)
async def get_huddle(
    huddle_id: str,
    user=Depends(get_admin_user),
):
    """Get huddle details (admin only)."""
    huddle = Huddles.get_huddle_by_id(huddle_id)
    if not huddle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Huddle not found",
        )
    return huddle

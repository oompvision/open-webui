"""
Huddle (Tenant) Middleware for Multi-Tenancy Support

This middleware extracts the huddle from the subdomain of incoming requests
and attaches it to the request state for use throughout the application.

Example:
    Request to: hoosiers-football.alumnihuddle.com
    Extracts slug: "hoosiers-football"
    Looks up huddle in database
    Attaches huddle to request.state.tenant
"""

import logging
import os
import time
from typing import Optional, Dict, Tuple

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from open_webui.models.tenants import Huddles, HuddleModel

log = logging.getLogger(__name__)

# Simple in-memory cache for huddle lookups to reduce database queries
# Format: {slug: (huddle, timestamp)}
_huddle_cache: Dict[str, Tuple[Optional[HuddleModel], float]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


def get_cached_huddle(slug: str) -> Optional[HuddleModel]:
    """Get huddle from cache or database, with TTL-based expiration."""
    now = time.time()

    # Check cache first
    if slug in _huddle_cache:
        huddle, cached_at = _huddle_cache[slug]
        if now - cached_at < CACHE_TTL_SECONDS:
            return huddle

    # Cache miss or expired - lookup from database
    try:
        huddle = Huddles.get_huddle_by_slug(slug)
        _huddle_cache[slug] = (huddle, now)
        return huddle
    except Exception as e:
        # On error, return cached value if available (even if expired)
        if slug in _huddle_cache:
            log.warning(f"Database error, using stale cache for {slug}: {e}")
            return _huddle_cache[slug][0]
        raise


# Configuration from environment variables
BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "alumnihuddle.com")
ENABLE_MULTI_TENANCY = os.environ.get("ENABLE_MULTI_TENANCY", "true").lower() == "true"
# Default tenant for localhost development/testing
DEFAULT_TENANT_SLUG = os.environ.get("DEFAULT_TENANT_SLUG", None)

# Subdomains that should NOT be treated as huddle slugs
RESERVED_SUBDOMAINS = {"www", "api", "admin", "app", "localhost"}


def extract_subdomain(host: str) -> Optional[str]:
    """
    Extract the huddle slug from the request host.

    Examples:
        hoosiers-football.alumnihuddle.com -> "hoosiers-football"
        www.alumnihuddle.com -> None (reserved)
        alumnihuddle.com -> None (no subdomain)
        localhost:3000 -> None (development)
    """
    if not host:
        return None

    # Remove port if present
    host = host.split(":")[0]

    # Handle localhost for development
    if host in ("localhost", "127.0.0.1"):
        # In development, check for X-Tenant-Subdomain header instead
        return None

    # Check if this is the base domain
    if not host.endswith(BASE_DOMAIN):
        return None

    # Extract subdomain
    subdomain_part = host[: -len(BASE_DOMAIN)].rstrip(".")

    if not subdomain_part:
        return None

    # Handle nested subdomains (take the first part)
    parts = subdomain_part.split(".")

    # If single part, check if reserved
    if len(parts) == 1:
        if parts[0].lower() in RESERVED_SUBDOMAINS:
            return None
        return parts[0].lower()

    # If multiple parts, find the huddle slug
    # Skip reserved subdomains from the left
    for part in parts:
        if part.lower() not in RESERVED_SUBDOMAINS:
            return part.lower()

    return None


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts huddle information from the request subdomain
    and attaches it to the request state.

    Usage in routes:
        @router.get("/")
        async def my_route(request: Request):
            huddle = request.state.tenant  # HuddleModel or None
            if huddle:
                print(f"Request from huddle: {huddle.name}")
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Initialize huddle as None
        request.state.tenant = None
        request.state.tenant_id = None
        request.state.huddle = None
        request.state.huddle_id = None

        if not ENABLE_MULTI_TENANCY:
            return await call_next(request)

        # Try to get slug from host
        host = request.headers.get("host", "")
        slug = extract_subdomain(host)

        # In development, allow header override for testing
        if slug is None:
            slug = request.headers.get("x-tenant-subdomain")

        # Fall back to default tenant for localhost development
        if slug is None and DEFAULT_TENANT_SLUG:
            slug = DEFAULT_TENANT_SLUG
            log.debug(f"Using default tenant slug: {slug}")

        if slug:
            # Look up huddle with caching to reduce database load
            try:
                huddle = get_cached_huddle(slug)

                if huddle:
                    # Set both tenant and huddle for compatibility
                    request.state.tenant = huddle
                    request.state.tenant_id = huddle.id
                    request.state.huddle = huddle
                    request.state.huddle_id = huddle.id
                    log.debug(f"Huddle identified: {huddle.name} ({huddle.slug})")
                else:
                    log.warning(f"Unknown huddle slug: {slug}")

            except HTTPException:
                raise
            except Exception as e:
                log.error(f"Error looking up huddle: {e}")

        return await call_next(request)


def get_current_tenant(request: Request) -> Optional[HuddleModel]:
    """
    Dependency function to get the current huddle from request state.
    Uses 'tenant' name for backward compatibility.
    """
    return getattr(request.state, "tenant", None)


def get_current_huddle(request: Request) -> Optional[HuddleModel]:
    """
    Dependency function to get the current huddle from request state.
    """
    return getattr(request.state, "huddle", None)


def require_tenant(request: Request) -> HuddleModel:
    """
    Dependency function that requires a valid huddle.
    Raises 400 error if no huddle is found.
    """
    huddle = getattr(request.state, "tenant", None)
    if not huddle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint requires a valid organization subdomain.",
        )
    return huddle


def require_huddle(request: Request) -> HuddleModel:
    """
    Dependency function that requires a valid huddle.
    Raises 400 error if no huddle is found.
    """
    return require_tenant(request)

"""
AlumniHuddle Extended App

This module wraps the OpenWebUI app and adds AlumniHuddle-specific routes and middleware.
Use this as the entry point instead of open_webui.main:app
"""

import logging
import os

# Import the original app
from open_webui.main import app

# Import our custom routers
from open_webui.routers.tenants import router as tenants_router
from open_webui.routers.mentors import router as mentors_router

log = logging.getLogger(__name__)

ENABLE_MULTI_TENANCY = os.environ.get("ENABLE_MULTI_TENANCY", "false").lower() == "true"


def init_huddle_models():
    """Initialize huddle-specific models on startup."""
    try:
        from open_webui.services.huddle_models import ensure_all_huddle_models
        count = ensure_all_huddle_models()
        log.info(f"AlumniHuddle: Initialized {count} huddle models")
    except Exception as e:
        log.error(f"AlumniHuddle: Failed to initialize huddle models: {e}")


def setup_alumnihuddle():
    """Setup AlumniHuddle customizations on the app."""

    if ENABLE_MULTI_TENANCY:
        # Middleware order is LIFO for requests:
        # - Last added runs FIRST on request
        # - First added runs LAST on request (and first on response)
        #
        # We need:
        # 1. Tenant middleware to set huddle context FIRST (on request)
        # 2. Model filter to read context and filter response
        #
        # So we add tenant middleware LAST (runs first on request)
        # and model filter FIRST (runs after tenant sets context)

        # Add tenant middleware to set huddle context on requests
        from open_webui.middleware.tenant import TenantMiddleware
        app.add_middleware(TenantMiddleware)
        log.info("AlumniHuddle: Tenant middleware enabled")

        # Note: Model filtering is now done directly in main.py's /api/models endpoint
        # This avoids issues with response compression (brotli/gzip)

        # Find the position of the SPA mount (usually the last route that catches all)
        # We need to insert our routes BEFORE it
        spa_mount_index = None
        for i, route in enumerate(app.routes):
            # Look for the SPAStaticFiles mount (catches all unmatched routes)
            if hasattr(route, 'app') and type(route.app).__name__ == 'SPAStaticFiles':
                spa_mount_index = i
                break

        if spa_mount_index is not None:
            # Insert our routes before the SPA mount
            log.info(f"AlumniHuddle: Inserting tenant routes before SPA mount at index {spa_mount_index}")

            # Remove the SPA mount temporarily
            spa_mount = app.routes.pop(spa_mount_index)

            # Add our routers
            app.include_router(tenants_router, prefix="/api/v1/tenants", tags=["tenants"])
            app.include_router(mentors_router, prefix="/api/v1/mentors", tags=["mentors"])

            # Re-add the SPA mount at the end
            app.routes.append(spa_mount)

            log.info("AlumniHuddle: Tenant API routes mounted at /api/v1/tenants")
            log.info("AlumniHuddle: Mentor API routes mounted at /api/v1/mentors")
        else:
            # No SPA mount found, just add normally
            app.include_router(tenants_router, prefix="/api/v1/tenants", tags=["tenants"])
            app.include_router(mentors_router, prefix="/api/v1/mentors", tags=["mentors"])
            log.info("AlumniHuddle: Tenant API routes mounted at /api/v1/tenants (no SPA mount found)")
            log.info("AlumniHuddle: Mentor API routes mounted at /api/v1/mentors (no SPA mount found)")

    log.info("AlumniHuddle initialization complete")


# Register startup event to initialize huddle models
@app.on_event("startup")
async def on_startup():
    """Called when the app starts up."""
    if ENABLE_MULTI_TENANCY:
        # Initialize huddle models after database is ready
        init_huddle_models()


# Run setup when this module is imported
setup_alumnihuddle()

# Export the app for uvicorn
__all__ = ["app"]

"""
AlumniHuddle Initialization

This module is imported to add multi-tenancy support to OpenWebUI.
It registers the tenant middleware with the FastAPI application.
"""

import logging
import os

log = logging.getLogger(__name__)

ENABLE_MULTI_TENANCY = os.environ.get("ENABLE_MULTI_TENANCY", "false").lower() == "true"


def register_tenant_middleware(app):
    """
    Register the tenant middleware with the FastAPI app.

    Call this function after the app is created to add multi-tenancy support.
    """
    if not ENABLE_MULTI_TENANCY:
        log.info("Multi-tenancy is disabled")
        return

    from open_webui.middleware.tenant import TenantMiddleware

    app.add_middleware(TenantMiddleware)
    log.info("AlumniHuddle: Tenant middleware registered")


def init_alumnihuddle(app):
    """
    Initialize all AlumniHuddle customizations.
    """
    log.info("Initializing AlumniHuddle customizations...")
    register_tenant_middleware(app)
    log.info("AlumniHuddle initialization complete")

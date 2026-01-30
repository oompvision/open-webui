"""
Model Filter Middleware for AlumniHuddle

Filters the /api/models response to only show the current huddle's model.
This ensures users only see ONE model - their huddle's branded mentor coach.
"""

import gzip
import json
import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.types import ASGIApp

from open_webui.services.huddle_models import get_huddle_model_id

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class HuddleModelFilterMiddleware(BaseHTTPMiddleware):
    """
    Middleware that filters model lists to only show the current huddle's model.

    When a user accesses /api/models or /api/v1/models, this middleware:
    1. Checks if there's a huddle in the request context
    2. If so, filters the response to only include that huddle's model
    3. Hides all raw Claude/pipeline models
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only intercept /api/models endpoints
        path = request.url.path
        if path not in ["/api/models", "/api/v1/models"]:
            return await call_next(request)

        log.info(f"Model filter middleware intercepting: {path}")
        print(f"[MODEL_FILTER] Intercepting: {path}")

        # Get the response first
        response = await call_next(request)

        # Check if we have a huddle in the request state
        huddle = getattr(request.state, "huddle", None) or getattr(request.state, "tenant", None)

        log.info(f"Huddle context in model filter: {huddle.slug if huddle else 'None'}")
        print(f"[MODEL_FILTER] Huddle context: {huddle.slug if huddle else 'None'}")

        if not huddle:
            # No huddle context - return original response
            log.warning("No huddle context found, returning unfiltered models")
            return response

        # We need to filter the response
        # Only process JSON responses
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        try:
            # Read the response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            # Check if response is gzipped
            content_encoding = response.headers.get("content-encoding", "")
            if content_encoding == "gzip":
                try:
                    body = gzip.decompress(body)
                except Exception as e:
                    log.error(f"Failed to decompress gzip response: {e}")
                    return response

            # Parse the JSON
            data = json.loads(body.decode("utf-8"))

            # Filter models to only include the huddle's model
            huddle_model_id = get_huddle_model_id(huddle)

            if "data" in data and isinstance(data["data"], list):
                # Filter to only show the huddle's model
                filtered_models = [
                    model for model in data["data"]
                    if model.get("id") == huddle_model_id
                ]

                # If the huddle model exists, only show that
                # Otherwise fall back to showing nothing (the model should be created)
                data["data"] = filtered_models

                log.info(f"Filtered models for huddle {huddle.slug}: showing {len(filtered_models)} models (looking for {huddle_model_id})")
                print(f"[MODEL_FILTER] Filtered to {len(filtered_models)} models for {huddle.slug} (looking for {huddle_model_id})")

            # Return the filtered response
            filtered_body = json.dumps(data).encode("utf-8")

            # Create new headers without Content-Length and Content-Encoding
            # (we're returning uncompressed data)
            new_headers = {
                k: v for k, v in response.headers.items()
                if k.lower() not in ["content-length", "content-encoding"]
            }

            return Response(
                content=filtered_body,
                status_code=response.status_code,
                headers=new_headers,
                media_type="application/json",
            )

        except Exception as e:
            log.error(f"Error filtering models response: {e}")
            # On error, return original response body
            new_headers = {
                k: v for k, v in response.headers.items()
                if k.lower() not in ["content-length", "content-encoding"]
            }
            return Response(
                content=body,
                status_code=response.status_code,
                headers=new_headers,
            )

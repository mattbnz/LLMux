"""
FastAPI middleware for API key validation.

Security features:
- Validates API key header on all /v1/ endpoints
- Uses timing-safe comparison via APIKeyStorage
- Logs failed validation attempts (with partial key only)
- Allows bypass for health/status endpoints
- Supports Tailscale identity headers for management API authentication

Tailscale auto-key support for /v1/ endpoints:
- Keys with names starting with "auto-" are only valid from Tailscale connections
- When an unknown key is provided from a Tailscale connection, a new key is
  automatically created with name format: auto-{tailscale_user}-{key}
- This allows API clients on the tailnet to use any key value they choose,
  which will be automatically registered on first use
"""
import logging
import os
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from utils.api_key_storage import APIKeyStorage

logger = logging.getLogger(__name__)

# Enable Tailscale header authentication (for requests via tailscale serve)
TAILSCALE_AUTH_ENABLED = os.getenv("TAILSCALE_AUTH_ENABLED", "true").lower() in ("true", "1", "yes")

# Endpoints that don't require API key authentication
EXEMPT_PATHS = {
    "/",
    "/health",
    "/healthz",
    "/auth/status",
    "/docs",
    "/openapi.json",
    "/redoc",
}

# Path prefixes that don't require API key authentication
EXEMPT_PREFIXES = (
    "/ui/",              # Web UI static files (auth handled by frontend)
)

# Management API paths that don't require authentication (OAuth callbacks)
MANAGEMENT_EXEMPT_PATHS = {
    "/api/management/auth/claude/callback",
    "/api/management/auth/claude/callback-long-term",
    "/api/management/auth/chatgpt/callback",
}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware to validate API keys on incoming requests"""

    def __init__(self, app):
        super().__init__(app)
        self.storage = APIKeyStorage()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip exempt paths
        if path in EXEMPT_PATHS:
            return await call_next(request)

        # Skip exempt prefixes (web UI static files)
        if path.startswith(EXEMPT_PREFIXES):
            return await call_next(request)

        # Skip management OAuth callback paths (these need to work without auth)
        if path in MANAGEMENT_EXEMPT_PATHS:
            return await call_next(request)

        # Validate management API endpoints with API key
        if path.startswith("/api/management/"):
            return await self._validate_management_request(request, call_next)

        # Only validate /v1/ API endpoints
        if not path.startswith("/v1/"):
            return await call_next(request)

        # Extract API key from headers
        api_key = self._extract_api_key(request)

        if not api_key:
            logger.warning(f"API key validation failed: no key provided for {path}")
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "message": "API key required. Provide Authorization: Bearer <key> or X-API-Key header.",
                        "type": "authentication_error",
                        "code": 401
                    }
                }
            )

        # Check for Tailscale identity (used for auto- key validation and dynamic creation)
        tailscale_user = None
        if TAILSCALE_AUTH_ENABLED:
            tailscale_user = self._extract_tailscale_identity(request)

        # Validate the key (timing-safe comparison happens in storage)
        key_id = self.storage.validate_key(api_key)

        if key_id:
            # Key exists - check if it's an auto- key that requires Tailscale
            key_info = self.storage.get_key_by_id(key_id)
            if key_info and key_info.get("name", "").startswith("auto-"):
                # Auto-keys only work from Tailscale connections
                if not tailscale_user:
                    logger.warning(f"Auto-key used from non-Tailscale connection: key_id={key_id}")
                    return JSONResponse(
                        status_code=401,
                        content={
                            "error": {
                                "message": "This API key is only valid when accessed via Tailscale.",
                                "type": "authentication_error",
                                "code": 401
                            }
                        }
                    )
                logger.debug(f"Auto-key validated via Tailscale: key_id={key_id}, user={tailscale_user['login']}")

            # Store key_id in request state for potential audit logging
            request.state.api_key_id = key_id
            return await call_next(request)

        # Key doesn't exist - check if we can auto-create it via Tailscale
        if tailscale_user:
            # Create new auto-key with format: auto-{tailscale_user}-{key}
            key_name = f"auto-{tailscale_user['login']}-{api_key}"
            key_id = self.storage.create_key_with_value(key_name, api_key)
            logger.info(f"Auto-created API key via Tailscale: key_id={key_id}, user={tailscale_user['login']}")

            request.state.api_key_id = key_id
            request.state.tailscale_user = tailscale_user
            return await call_next(request)

        # No valid key and no Tailscale auth - reject
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "message": "Invalid API key.",
                    "type": "authentication_error",
                    "code": 401
                }
            }
        )

    async def _validate_management_request(self, request: Request, call_next):
        """Validate management API requests with API key or Tailscale identity"""
        path = request.url.path

        # Check for Tailscale identity headers first (if enabled)
        if TAILSCALE_AUTH_ENABLED:
            tailscale_user = self._extract_tailscale_identity(request)
            if tailscale_user:
                logger.debug(f"Tailscale auth for {path}: {tailscale_user['login']}")
                request.state.tailscale_user = tailscale_user
                request.state.api_key_id = f"tailscale:{tailscale_user['login']}"
                return await call_next(request)

        # Fall back to API key authentication
        api_key = self._extract_api_key(request)

        if not api_key:
            logger.warning(f"Management API key validation failed: no key provided for {path}")
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "message": "API key required for management API. Provide Authorization: Bearer <key> or X-API-Key header.",
                        "type": "authentication_error",
                        "code": 401
                    }
                }
            )

        # Validate the key
        key_id = self.storage.validate_key(api_key)
        if not key_id:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "message": "Invalid API key.",
                        "type": "authentication_error",
                        "code": 401
                    }
                }
            )

        # Store key_id in request state
        request.state.api_key_id = key_id
        return await call_next(request)

    def _extract_api_key(self, request: Request) -> str | None:
        """Extract API key from request headers.

        Returns any key provided in Authorization (Bearer) or X-API-Key headers.
        Keys don't need to start with 'llmux-' - arbitrary keys are allowed
        for Tailscale auto-key creation (see docstring at module level).
        """
        # Get auth-related headers
        auth_header = request.headers.get("Authorization", "")
        x_api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")

        # Debug: log what headers we received (truncated for security)
        if auth_header:
            logger.debug(f"Authorization header: {auth_header[:30]}...")
        if x_api_key:
            logger.debug(f"X-API-Key header: {x_api_key[:20]}...")
        if not auth_header and not x_api_key:
            logger.debug(f"No auth headers found. All headers: {list(request.headers.keys())}")

        # Check Authorization header first (Bearer token format)
        if auth_header.lower().startswith("bearer "):
            potential_key = auth_header[7:].strip()  # Remove "Bearer " prefix
            if potential_key:
                return potential_key

        # Check X-API-Key header as alternative
        if x_api_key:
            return x_api_key

        return None

    def _extract_tailscale_identity(self, request: Request) -> dict | None:
        """Extract Tailscale identity from headers set by tailscale serve.

        Tailscale serve adds these headers for tailnet traffic:
        - Tailscale-User-Login: User's login (e.g., alice@example.com)
        - Tailscale-User-Name: User's display name
        - Tailscale-User-Profile-Pic: Profile picture URL (optional)

        Returns dict with user info if headers present, None otherwise.
        """
        login = request.headers.get("Tailscale-User-Login")

        if not login:
            return None

        # Decode RFC2047 "Q" encoding if present (for non-ASCII values)
        name = request.headers.get("Tailscale-User-Name", "")
        profile_pic = request.headers.get("Tailscale-User-Profile-Pic", "")

        return {
            "login": login,
            "name": name,
            "profile_pic": profile_pic,
        }

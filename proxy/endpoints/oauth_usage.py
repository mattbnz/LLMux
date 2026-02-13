"""
OAuth usage endpoint - proxies Anthropic's usage API with caching.

Forwards GET requests to https://api.anthropic.com/api/oauth/usage
with a 60-second cache to prevent excessive requests when multiple
LLMux clients check usage data.
"""
import json
import logging
import time
from typing import Optional, Tuple

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response

from oauth import OAuthManager
from headers import USER_AGENT
from settings import REQUEST_TIMEOUT, CONNECT_TIMEOUT

logger = logging.getLogger(__name__)
router = APIRouter()
oauth_manager = OAuthManager()

ANTHROPIC_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
CACHE_TTL_SECONDS = 60


class _UsageCache:
    """Simple cache for OAuth usage responses with 60-second TTL."""

    def __init__(self, ttl_seconds: int = CACHE_TTL_SECONDS):
        self._cached_response: Optional[Tuple[bytes, int, float]] = None
        self._ttl = ttl_seconds

    def get(self) -> Optional[Tuple[bytes, int]]:
        """Return cached (content, status_code) if valid, None if expired."""
        if not self._cached_response:
            return None
        content, status_code, timestamp = self._cached_response
        if time.time() - timestamp > self._ttl:
            self._cached_response = None
            return None
        return (content, status_code)

    def put(self, content: bytes, status_code: int) -> None:
        """Cache response content and status code with current timestamp."""
        self._cached_response = (content, status_code, time.time())


# Global cache instance
_usage_cache = _UsageCache()


@router.get("/api/oauth/usage")
async def oauth_usage(raw_request: Request):
    """Proxy OAuth usage endpoint with 60-second caching.

    Forwards the request to Anthropic's usage API, adding required headers.
    Caches successful responses for 60 seconds to prevent excessive requests
    when multiple LLMux clients check usage data.
    """
    # Check cache first
    cached = _usage_cache.get()
    if cached is not None:
        content, status_code = cached
        logger.debug("Returning cached usage response")
        return Response(
            content=content,
            status_code=status_code,
            media_type="application/json",
        )

    logger.info("Fetching fresh usage data from Anthropic API")

    # Get valid OAuth token
    access_token = await oauth_manager.get_valid_token_async()
    if not access_token:
        return Response(
            content=json.dumps({
                "error": {
                    "type": "authentication_error",
                    "message": "OAuth expired; please authenticate using the CLI"
                }
            }),
            status_code=401,
            media_type="application/json",
        )

    # Build headers with required OAuth beta and User-Agent
    headers = {
        "authorization": f"Bearer {access_token}",
        "anthropic-beta": "oauth-2025-04-20",
        "User-Agent": USER_AGENT,
    }

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT)
        ) as client:
            response = await client.get(ANTHROPIC_USAGE_URL, headers=headers)

        logger.info(f"Anthropic usage API responded with status={response.status_code}")

        # Cache successful responses
        if response.status_code == 200:
            _usage_cache.put(response.content, response.status_code)
            logger.debug(f"Cached usage response for {CACHE_TTL_SECONDS} seconds")

        # Return the raw Anthropic response
        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type="application/json",
        )

    except httpx.TimeoutException:
        logger.error("Timeout while fetching usage data from Anthropic API")
        return Response(
            content=json.dumps({
                "error": {
                    "type": "timeout_error",
                    "message": "Timeout while fetching usage data"
                }
            }),
            status_code=504,
            media_type="application/json",
        )
    except Exception as e:
        logger.error(f"Error fetching usage data: {e}")
        return Response(
            content=json.dumps({
                "error": {
                    "type": "internal_error",
                    "message": f"Failed to fetch usage data: {str(e)}"
                }
            }),
            status_code=500,
            media_type="application/json",
        )

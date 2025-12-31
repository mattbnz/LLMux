"""
Central utility for recording API usage from endpoints.

Provides a simple interface for recording usage that handles
storage initialization and error handling.
"""
import logging
from typing import Optional

from .usage_storage import UsageStorage

logger = logging.getLogger(__name__)

# Singleton storage instance
_storage: Optional[UsageStorage] = None


def get_storage() -> UsageStorage:
    """Get or create the singleton storage instance."""
    global _storage
    if _storage is None:
        _storage = UsageStorage()
    return _storage


def record_request_usage(
    key_id: Optional[str],
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
    request_id: str = ""
):
    """Record usage for a completed API request.

    This is the main entry point for recording usage from endpoint handlers.
    It handles missing key_id gracefully and catches any storage errors
    to prevent usage tracking from breaking API requests.

    Args:
        key_id: The API key ID (may be None if no key validation occurred)
        model: The Anthropic model used
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cache_read_tokens: Tokens read from cache (optional)
        cache_creation_tokens: Tokens written to cache (optional)
        request_id: Request ID for logging (optional)
    """
    if not key_id:
        logger.debug(f"[{request_id}] No key_id available, skipping usage recording")
        return

    if input_tokens == 0 and output_tokens == 0:
        logger.debug(f"[{request_id}] No tokens to record, skipping usage recording")
        return

    try:
        storage = get_storage()
        storage.record_usage(
            key_id=key_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_creation_tokens=cache_creation_tokens
        )
        logger.debug(
            f"[{request_id}] Recorded usage: key={key_id[:8]}..., model={model}, "
            f"in={input_tokens}, out={output_tokens}, "
            f"cache_read={cache_read_tokens}, cache_create={cache_creation_tokens}"
        )
    except Exception as e:
        # Log error but don't fail the request
        logger.error(f"[{request_id}] Failed to record usage: {e}")

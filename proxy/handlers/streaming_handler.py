"""
Streaming response handlers for Anthropic and OpenAI formats.
"""
import json
import logging
from typing import Dict, Any, Optional, AsyncIterator, Callable

from anthropic import stream_anthropic_response
from openai_compat import convert_anthropic_stream_to_openai
from stream_debug import StreamTracer

logger = logging.getLogger(__name__)


async def create_anthropic_stream(
    request_id: str,
    anthropic_request: Dict[str, Any],
    access_token: str,
    client_beta_headers: Optional[str],
    tracer: Optional[StreamTracer] = None,
) -> AsyncIterator[bytes]:
    """
    Create a streaming response in Anthropic format.

    Args:
        request_id: Request ID for logging
        anthropic_request: Prepared Anthropic request
        access_token: OAuth access token
        client_beta_headers: Beta feature headers from client
        tracer: Optional stream tracer for debugging

    Yields:
        Raw SSE chunks in bytes
    """
    async for chunk in stream_anthropic_response(
        request_id,
        anthropic_request,
        access_token,
        client_beta_headers,
        tracer=tracer,
    ):
        yield chunk


async def create_openai_stream(
    request_id: str,
    anthropic_request: Dict[str, Any],
    access_token: str,
    client_beta_headers: Optional[str],
    model: str,
    tracer: Optional[StreamTracer] = None,
    include_usage: bool = False,
    usage_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> AsyncIterator[bytes]:
    """
    Create a streaming response in OpenAI format.

    Args:
        request_id: Request ID for logging
        anthropic_request: Prepared Anthropic request
        access_token: OAuth access token
        client_beta_headers: Beta feature headers from client
        model: Model name for OpenAI response
        tracer: Optional stream tracer for debugging
        include_usage: If True, include usage in final chunk (OpenAI stream_options)
        usage_callback: Optional callback invoked with usage data after stream completes

    Yields:
        SSE chunks in OpenAI format
    """
    # Track usage from raw Anthropic stream for callback
    stream_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }

    async def tracked_anthropic_stream():
        """Wrapper that tracks usage from Anthropic SSE events."""
        async for chunk in stream_anthropic_response(
            request_id,
            anthropic_request,
            access_token,
            client_beta_headers,
            tracer=tracer,
        ):
            # Parse SSE chunk to extract usage
            if chunk and b'"usage"' in chunk:
                try:
                    for line in chunk.decode('utf-8', errors='ignore').split('\n'):
                        if line.startswith('data: '):
                            data = json.loads(line[6:])
                            if data.get("type") == "message_start":
                                message = data.get("message", {})
                                usage = message.get("usage", {})
                                stream_usage["input_tokens"] = usage.get("input_tokens", 0)
                                stream_usage["cache_read_input_tokens"] = usage.get("cache_read_input_tokens", 0)
                                stream_usage["cache_creation_input_tokens"] = usage.get("cache_creation_input_tokens", 0)
                            elif data.get("type") == "message_delta":
                                usage = data.get("usage", {})
                                if usage.get("output_tokens"):
                                    stream_usage["output_tokens"] = usage.get("output_tokens", 0)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
            yield chunk

    # Convert to OpenAI format
    try:
        async for chunk in convert_anthropic_stream_to_openai(
            tracked_anthropic_stream(),
            model,
            request_id,
            tracer=tracer,
            include_usage=include_usage,
        ):
            yield chunk
    finally:
        # Invoke usage callback after stream completes
        if usage_callback and (stream_usage["input_tokens"] > 0 or stream_usage["output_tokens"] > 0):
            try:
                usage_callback(stream_usage)
            except Exception as e:
                logger.error(f"[{request_id}] Usage callback error: {e}")

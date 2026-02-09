"""
Native Anthropic messages endpoint - pure pass-through proxy.

Forwards request bodies to the Anthropic API without modification.
Only responsibilities:
  1. OAuth token injection (swap client auth for LLMux's Bearer token)
  2. Required header spoofing (User-Agent, x-app, etc. for OAuth validation)
  3. Token usage tracking from responses
"""
import json
import logging
import time
import uuid

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse

from oauth import OAuthManager
from headers import USER_AGENT, X_APP_HEADER, STAINLESS_HEADERS
from settings import STREAM_TIMEOUT, REQUEST_TIMEOUT, CONNECT_TIMEOUT, READ_TIMEOUT
from utils.usage_recorder import record_request_usage

logger = logging.getLogger(__name__)
router = APIRouter()
oauth_manager = OAuthManager()

# Beta headers required for OAuth authentication
REQUIRED_BETAS = ["oauth-2025-04-20", "claude-code-20250219"]

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"


def _merge_beta_headers(client_betas: str) -> str:
    """Merge client beta headers with required OAuth betas, preserving order."""
    betas = list(REQUIRED_BETAS)
    if client_betas:
        client_list = [b.strip() for b in client_betas.split(",") if b.strip()]
        # Preserve order, deduplicate
        betas = list(dict.fromkeys(betas + client_list))
    return ",".join(betas)


@router.post("/v1/messages")
async def anthropic_messages(raw_request: Request):
    """Pure pass-through proxy to the Anthropic Messages API.

    The request body is forwarded byte-for-byte - no Pydantic parsing,
    no sanitization, no parameter injection. This ensures forward
    compatibility with any new API features or parameter shapes.
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    # Read the raw body - we forward this as-is
    body = await raw_request.body()

    # Minimal parse to determine streaming mode and model (for usage tracking)
    try:
        request_data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return Response(
            content=json.dumps({"error": {"type": "invalid_request_error", "message": "Invalid JSON body"}}),
            status_code=400,
            media_type="application/json",
        )

    model = request_data.get("model", "unknown")
    is_streaming = request_data.get("stream", False)

    logger.info(f"[{request_id}] Anthropic pass-through: model={model} stream={is_streaming}")

    # Get valid OAuth token
    access_token = await oauth_manager.get_valid_token_async()
    if not access_token:
        return Response(
            content=json.dumps({"error": {"type": "authentication_error", "message": "OAuth expired; please authenticate using the CLI"}}),
            status_code=401,
            media_type="application/json",
        )

    # Build outbound headers:
    #   - OAuth Bearer token (required)
    #   - Spoof headers so Anthropic accepts the OAuth session (required)
    #   - Client's anthropic-beta merged with required OAuth betas
    #   - Client's anthropic-version passed through
    client_beta = raw_request.headers.get("anthropic-beta", "")
    headers = {
        "authorization": f"Bearer {access_token}",
        "anthropic-version": raw_request.headers.get("anthropic-version", "2023-06-01"),
        "content-type": "application/json",
        "anthropic-beta": _merge_beta_headers(client_beta),
        "User-Agent": USER_AGENT,
        "x-app": X_APP_HEADER,
        **STAINLESS_HEADERS,
    }

    api_key_id = getattr(raw_request.state, "api_key_id", None)

    try:
        if is_streaming:
            return await _handle_streaming(request_id, body, headers, model, api_key_id, start_time)
        else:
            return await _handle_non_streaming(request_id, body, headers, model, api_key_id, start_time)
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"[{request_id}] Request failed after {elapsed_ms}ms: {e}")
        return Response(
            content=json.dumps({"error": {"type": "internal_error", "message": str(e)}}),
            status_code=500,
            media_type="application/json",
        )


async def _handle_streaming(request_id, body, headers, model, api_key_id, start_time):
    """Stream response from Anthropic, extracting usage data for tracking."""

    usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }

    async def stream_generator():
        nonlocal usage
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(STREAM_TIMEOUT, connect=CONNECT_TIMEOUT, read=READ_TIMEOUT)
            ) as client:
                async with client.stream(
                    "POST", ANTHROPIC_API_URL, content=body, headers=headers,
                ) as response:
                    if response.status_code != 200:
                        error_bytes = await response.aread()
                        logger.error(f"[{request_id}] Anthropic API error {response.status_code}: {error_bytes.decode(errors='replace')}")
                        yield f"event: error\ndata: {error_bytes.decode(errors='replace')}\n\n"
                        return

                    async for chunk in response.aiter_text():
                        if chunk and '"usage"' in chunk:
                            _extract_stream_usage(chunk, usage)
                        yield chunk

        except httpx.ReadTimeout:
            yield f'event: error\ndata: {{"error": {{"type": "timeout_error", "message": "Stream read timeout"}}}}\n\n'
        except httpx.RemoteProtocolError as e:
            yield f'event: error\ndata: {{"error": {{"type": "api_error", "message": "Connection closed: {e}"}}}}\n\n'
        finally:
            elapsed_ms = int((time.time() - start_time) * 1000)
            if usage["input_tokens"] > 0 or usage["output_tokens"] > 0:
                record_request_usage(
                    key_id=api_key_id,
                    model=model,
                    input_tokens=usage["input_tokens"],
                    output_tokens=usage["output_tokens"],
                    cache_read_tokens=usage["cache_read_input_tokens"],
                    cache_creation_tokens=usage["cache_creation_input_tokens"],
                    request_id=request_id,
                )
            logger.info(f"[{request_id}] Stream completed in {elapsed_ms}ms")

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


async def _handle_non_streaming(request_id, body, headers, model, api_key_id, start_time):
    """Forward non-streaming request, extract usage, return raw response."""

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT)
    ) as client:
        response = await client.post(ANTHROPIC_API_URL, content=body, headers=headers)

    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(f"[{request_id}] Anthropic responded in {elapsed_ms}ms status={response.status_code}")

    # Extract usage for tracking (best-effort, don't fail if response isn't JSON)
    if response.status_code == 200:
        try:
            response_data = json.loads(response.content)
            usage = response_data.get("usage", {})
            record_request_usage(
                key_id=api_key_id,
                model=model,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cache_read_tokens=usage.get("cache_read_input_tokens", 0),
                cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
                request_id=request_id,
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    # Return the raw Anthropic response byte-for-byte, preserving status code
    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type="application/json",
    )


def _extract_stream_usage(chunk: str, usage: dict) -> None:
    """Extract token usage from SSE stream chunks (best-effort)."""
    try:
        for line in chunk.split("\n"):
            if not line.startswith("data: "):
                continue
            data = json.loads(line[6:])
            event_type = data.get("type")
            if event_type == "message_start":
                msg_usage = data.get("message", {}).get("usage", {})
                usage["input_tokens"] = msg_usage.get("input_tokens", 0)
                usage["cache_read_input_tokens"] = msg_usage.get("cache_read_input_tokens", 0)
                usage["cache_creation_input_tokens"] = msg_usage.get("cache_creation_input_tokens", 0)
            elif event_type == "message_delta":
                delta_usage = data.get("usage", {})
                if delta_usage.get("output_tokens"):
                    usage["output_tokens"] = delta_usage["output_tokens"]
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass

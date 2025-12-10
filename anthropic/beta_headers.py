"""Beta header management for Anthropic API"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Core beta headers always required
CORE_BETAS = [
    "oauth-2025-04-20",       # OAuth authentication
    "claude-code-20250219",   # Claude Code features
]


def build_beta_headers(
    anthropic_request: Dict[str, Any],
    client_beta_headers: Optional[str] = None,
    request_id: Optional[str] = None,
    for_streaming: bool = False,
    reasoning_level: Optional[str] = None,
    use_1m_context: bool = False,
) -> str:
    """Build beta header value based on request features

    Args:
        anthropic_request: The Anthropic API request data
        client_beta_headers: Optional client-provided beta headers
        request_id: Optional request ID for logging
        for_streaming: Whether this is for a streaming request
        reasoning_level: Reasoning level from model resolution (e.g., "low", "medium", "high")
        use_1m_context: Whether 1M context is requested

    Returns:
        Comma-separated beta header value
    """
    # Start with core betas
    required_betas: List[str] = list(CORE_BETAS)

    # Always add tool streaming for tool-based requests
    if anthropic_request.get("tools"):
        required_betas.append("fine-grained-tool-streaming-2025-05-14")

    # Add 1M context beta if requested
    if use_1m_context or anthropic_request.get("_use_1m_context", False):
        required_betas.append("context-1m-2025-08-07")
        if request_id:
            logger.debug(f"[{request_id}] Adding context-1m beta (1M context model variant requested)")

    # Add thinking beta if enabled (either via request or reasoning_level)
    thinking = anthropic_request.get("thinking")
    thinking_enabled = thinking and thinking.get("type") == "enabled"
    if thinking_enabled or reasoning_level:
        required_betas.append("interleaved-thinking-2025-05-14")
        if request_id:
            logger.debug(f"[{request_id}] Adding interleaved-thinking beta (thinking enabled)")

    # Merge with client beta headers (preserve order, remove duplicates)
    if client_beta_headers:
        if for_streaming and request_id:
            logger.debug(f"[{request_id}] Client beta headers: {client_beta_headers}")

        client_betas = [beta.strip() for beta in client_beta_headers.split(",")]
        # Use dict.fromkeys to preserve order and remove duplicates
        required_betas = list(dict.fromkeys(required_betas + client_betas))

    beta_header_value = ",".join(required_betas)

    if request_id:
        logger.debug(f"[{request_id}] Final beta headers: {beta_header_value}")

    return beta_header_value

"""
Anthropic API pricing calculations.

Provides hardcoded pricing for Claude models and cost calculation functions.
Prices are in USD per million tokens.
"""
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ModelPricing:
    """Pricing information for a Claude model."""
    input_per_million: float
    output_per_million: float
    cache_read_discount: float = 0.90  # 90% discount for cache reads
    cache_write_premium: float = 1.25  # 25% premium for cache writes


# Current Anthropic pricing (per million tokens, USD)
# Updated: December 2024
MODEL_PRICING: Dict[str, ModelPricing] = {
    # Opus 4.5
    "claude-opus-4-5-20251101": ModelPricing(15.0, 75.0),

    # Sonnet 4.5
    "claude-sonnet-4-5-20250929": ModelPricing(3.0, 15.0),

    # Haiku 4.5
    "claude-haiku-4-5-20251001": ModelPricing(0.80, 4.0),

    # Opus 4.1
    "claude-opus-4-1-20250805": ModelPricing(15.0, 75.0),

    # Sonnet 4
    "claude-sonnet-4-20250514": ModelPricing(3.0, 15.0),

    # Legacy models (for reference)
    "claude-3-5-sonnet-20241022": ModelPricing(3.0, 15.0),
    "claude-3-5-haiku-20241022": ModelPricing(0.80, 4.0),
    "claude-3-opus-20240229": ModelPricing(15.0, 75.0),
}

# Default pricing for unknown models (uses Sonnet pricing as middle ground)
DEFAULT_PRICING = ModelPricing(3.0, 15.0)


# Model display names for UI
MODEL_DISPLAY_NAMES: Dict[str, str] = {
    "claude-opus-4-5-20251101": "Claude Opus 4.5",
    "claude-sonnet-4-5-20250929": "Claude Sonnet 4.5",
    "claude-haiku-4-5-20251001": "Claude Haiku 4.5",
    "claude-opus-4-1-20250805": "Claude Opus 4.1",
    "claude-sonnet-4-20250514": "Claude Sonnet 4",
    "claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet",
    "claude-3-5-haiku-20241022": "Claude 3.5 Haiku",
    "claude-3-opus-20240229": "Claude 3 Opus",
}


def get_model_pricing(model: str) -> ModelPricing:
    """Get pricing for a model, falling back to default for unknown models.

    Args:
        model: The model ID

    Returns:
        ModelPricing instance
    """
    return MODEL_PRICING.get(model, DEFAULT_PRICING)


def get_model_display_name(model: str) -> str:
    """Get human-readable display name for a model.

    Args:
        model: The model ID

    Returns:
        Display name string
    """
    if model in MODEL_DISPLAY_NAMES:
        return MODEL_DISPLAY_NAMES[model]

    # Generate a readable name from the model ID
    # e.g., "claude-sonnet-4-20250514" -> "Claude Sonnet 4"
    parts = model.replace("claude-", "").split("-")
    # Remove the date suffix if present
    if len(parts) > 1 and parts[-1].isdigit() and len(parts[-1]) == 8:
        parts = parts[:-1]
    return "Claude " + " ".join(p.capitalize() for p in parts)


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0
) -> float:
    """Calculate cost in USD for given token counts.

    The cost calculation accounts for:
    - Regular input tokens (excluding cache operations)
    - Cache read tokens (90% discount)
    - Cache creation tokens (25% premium)
    - Output tokens

    Args:
        model: The model ID
        input_tokens: Total input tokens (may include cache tokens)
        output_tokens: Number of output tokens
        cache_read_tokens: Tokens read from cache
        cache_creation_tokens: Tokens written to cache

    Returns:
        Cost in USD
    """
    pricing = get_model_pricing(model)

    # Calculate regular input tokens (excluding cache operations)
    # Note: cache_read_tokens and cache_creation_tokens are subsets of input_tokens
    regular_input = max(0, input_tokens - cache_read_tokens - cache_creation_tokens)

    cost = 0.0

    # Regular input cost
    cost += (regular_input / 1_000_000) * pricing.input_per_million

    # Cache read cost (with 90% discount)
    cache_read_rate = pricing.input_per_million * (1 - pricing.cache_read_discount)
    cost += (cache_read_tokens / 1_000_000) * cache_read_rate

    # Cache creation cost (with 25% premium)
    cache_create_rate = pricing.input_per_million * pricing.cache_write_premium
    cost += (cache_creation_tokens / 1_000_000) * cache_create_rate

    # Output cost
    cost += (output_tokens / 1_000_000) * pricing.output_per_million

    return cost


def calculate_cost_from_usage(usage: Dict) -> float:
    """Calculate cost from a usage dictionary.

    Convenience function that accepts a dictionary with usage data.

    Args:
        usage: Dictionary with keys:
            - model: Model ID
            - input_tokens or total_input_tokens
            - output_tokens or total_output_tokens
            - cache_read_tokens or total_cache_read_tokens (optional)
            - cache_creation_tokens or total_cache_creation_tokens (optional)

    Returns:
        Cost in USD
    """
    model = usage.get("model", "")
    input_tokens = usage.get("input_tokens", usage.get("total_input_tokens", 0))
    output_tokens = usage.get("output_tokens", usage.get("total_output_tokens", 0))
    cache_read = usage.get("cache_read_tokens", usage.get("total_cache_read_tokens", 0))
    cache_create = usage.get("cache_creation_tokens", usage.get("total_cache_creation_tokens", 0))

    return calculate_cost(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
        cache_creation_tokens=cache_create
    )


def format_cost(cost: float) -> str:
    """Format cost for display.

    Args:
        cost: Cost in USD

    Returns:
        Formatted string (e.g., "$0.42", "$1.23")
    """
    if cost < 0.01:
        return f"${cost:.4f}"
    elif cost < 1:
        return f"${cost:.2f}"
    else:
        return f"${cost:,.2f}"


def format_tokens(tokens: int) -> str:
    """Format token count for display.

    Args:
        tokens: Token count

    Returns:
        Formatted string (e.g., "1.2K", "1.5M")
    """
    if tokens < 1000:
        return str(tokens)
    elif tokens < 1_000_000:
        return f"{tokens / 1000:.1f}K"
    else:
        return f"{tokens / 1_000_000:.1f}M"

"""Model prices (USD per million tokens). Cached from the provider's list on 2026-09-25: re-check before relying on them."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    id: str
    input_per_mtok: float
    output_per_mtok: float
    supports_effort: bool  # output_config.effort is rejected by some older models
    thinking: dict | None = None  # request override used to keep extraction cheap


MODELS: dict[str, ModelSpec] = {
    "haiku": ModelSpec("claude-haiku-4-5", 1.00, 5.00, supports_effort=False),
    # Sonnet 5.5 thinks by default; "between_tools" turns thinking off for a pure extraction call.
    "sonnet": ModelSpec("claude-sonnet-5-5", 2.00, 10.00, supports_effort=True, thinking={"type": "between_tools"}),
    # Opus 5.5 cannot disable thinking; effort "low" is the only lever.
    "opus": ModelSpec("claude-opus-5-5", 4.00, 20.00, supports_effort=True),
}


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


def compute_cost(spec: ModelSpec, usage: Usage) -> float:
    """USD for one call. Cache reads cost 0.1x input, cache writes 1.25x."""
    inp = spec.input_per_mtok / 1_000_000
    return (
        usage.input_tokens * inp
        + usage.cache_read_tokens * inp * 0.1
        + usage.cache_write_tokens * inp * 1.25
        + usage.output_tokens * spec.output_per_mtok / 1_000_000
    )

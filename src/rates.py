"""
Cost-per-token rate card.

Rates are in USD per token. Kept as a plain dictionary so it's
easy to update without touching any other module.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelRate:
    prompt: float       # USD per token
    completion: float   # USD per token


# ── Rate card (public pricing) ───────────────────────────────
RATES: dict[str, ModelRate] = {
    # OpenAI
    "gpt-4o":           ModelRate(prompt=2.50e-6,  completion=10.00e-6),
    "gpt-4o-mini":      ModelRate(prompt=0.15e-6,  completion=0.60e-6),
    "gpt-4-turbo":      ModelRate(prompt=10.00e-6, completion=30.00e-6),
    "gpt-3.5-turbo":    ModelRate(prompt=0.50e-6,  completion=1.50e-6),
    # Anthropic
    "claude-sonnet-4-20250514":  ModelRate(prompt=3.00e-6,  completion=15.00e-6),
    "claude-haiku-3.5":          ModelRate(prompt=0.80e-6,  completion=4.00e-6),
}

# Fallback for unknown models — conservative estimate
DEFAULT_RATE = ModelRate(prompt=10.00e-6, completion=30.00e-6)


def get_rate(model: str) -> ModelRate:
    """Return the rate for a model, falling back to a conservative default."""
    return RATES.get(model, DEFAULT_RATE)

"""
Thin wrapper around litellm.acompletion that wires in the spend logger.

Usage:
    from src.llm_client import completion

    resp = await completion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello"}],
        user_id="alice",
        feature_name="chat",
    )
"""

import litellm
from litellm import ModelResponse

from src.spend_logger import log_spend

# Register the callback once at import time
litellm.success_callback = [log_spend]


async def completion(
    model: str,
    messages: list[dict],
    *,
    user_id: str = "unknown",
    feature_name: str | None = None,
    **kwargs,
) -> ModelResponse:
    """
    Call an LLM via LiteLLM and automatically log spend to Postgres.

    Parameters
    ----------
    model : str
        Model alias (must match a key in rates.py or LiteLLM's model list).
    messages : list[dict]
        OpenAI-style messages list.
    user_id : str
        Identifies the caller for cost attribution.
    feature_name : str | None
        Logical feature/product area (e.g. "summariser", "chat").
    **kwargs
        Forwarded to litellm.acompletion (temperature, max_tokens, etc.).
    """
    metadata = kwargs.pop("metadata", {}) or {}
    metadata["user_id"] = user_id
    metadata["feature_name"] = feature_name

    response: ModelResponse = await litellm.acompletion(
        model=model,
        messages=messages,
        metadata=metadata,
        **kwargs,
    )
    return response

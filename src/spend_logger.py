"""
LiteLLM success-callback that logs every completion to Postgres.

This module is the heart of the pipeline.  It:
  1. Extracts the usage block from the LLM response.
  2. Calculates cost from the local rate card (no external API).
  3. Asynchronously inserts a row into raw_spend_logs.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from litellm import ModelResponse

from src.db import get_pool
from src.rates import get_rate

logger = logging.getLogger(__name__)

INSERT_SQL = """
    INSERT INTO raw_spend_logs
        (request_id, user_id, feature_name, model, provider,
         prompt_tokens, completion_tokens, total_tokens,
         cost_usd, latency_ms, metadata, created_at)
    VALUES
        ($1, $2, $3, $4, $5,
         $6, $7, $8,
         $9, $10, $11, $12)
    ON CONFLICT (request_id) DO NOTHING;
"""


async def _async_log(kwargs: dict, response: ModelResponse) -> None:
    """Async insert of a single spend row."""
    try:
        usage = response.usage
        model: str = response.model or kwargs.get("model", "unknown")
        rate = get_rate(model)

        prompt_tokens = usage.prompt_tokens or 0
        completion_tokens = usage.completion_tokens or 0
        total_tokens = prompt_tokens + completion_tokens

        cost = (prompt_tokens * rate.prompt) + (completion_tokens * rate.completion)

        # Pull caller-supplied metadata from litellm_params or kwargs
        litellm_params: dict = kwargs.get("litellm_params", {}) or {}
        md: dict = litellm_params.get("metadata", {}) or {}

        user_id: str = md.get("user_id", "unknown")
        feature_name: str | None = md.get("feature_name")
        provider: str | None = md.get("custom_llm_provider") or litellm_params.get("custom_llm_provider")

        request_id = md.get("request_id", str(uuid.uuid4()))
        if isinstance(request_id, str):
            request_id = uuid.UUID(request_id)

        # Latency
        start = kwargs.get("start_time")
        end = kwargs.get("end_time")
        latency_ms: int | None = None
        if isinstance(start, datetime) and isinstance(end, datetime):
            latency_ms = int((end - start).total_seconds() * 1000)

        pool = await get_pool()
        await pool.execute(
            INSERT_SQL,
            request_id,
            user_id,
            feature_name,
            model,
            provider,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            cost,
            latency_ms,
            md,  # asyncpg serialises dict -> JSONB natively
            datetime.now(timezone.utc),
        )
        logger.debug("Logged spend: user=%s model=%s cost=$%.6f", user_id, model, cost)

    except Exception:
        # Never let logging failures crash the hot path
        logger.exception("spend_logger: failed to write spend row")


def log_spend(kwargs: dict, response: ModelResponse, *_args, **_kwargs) -> None:
    """
    Synchronous entry-point that LiteLLM calls.

    Schedules the real work onto the running event loop so the caller
    is not blocked.  If no loop is running, falls back to asyncio.run().
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_async_log(kwargs, response))
    except RuntimeError:
        asyncio.run(_async_log(kwargs, response))

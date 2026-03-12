"""Centralised configuration from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.environ["DATABASE_URL"]
OPENAI_API_KEY: str | None = os.environ.get("OPENAI_API_KEY")
ANTHROPIC_API_KEY: str | None = os.environ.get("ANTHROPIC_API_KEY")

# Watchdog threshold: projected daily cost that triggers an alert
DAILY_BUDGET_LIMIT_USD: float = float(os.environ.get("DAILY_BUDGET_LIMIT_USD", "50.0"))

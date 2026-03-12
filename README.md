# Token Burn 🔥

**An MVP-grade LLM cost monitoring system that tracks spend per user and feature in real time.**

Built with Python, PostgreSQL, and dbt — no managed services, no vendor lock-in, no third-party dashboards required.

---

## Why This Exists

LLM APIs bill per token, and costs compound fast. A single unmonitored feature calling GPT-4o can silently burn through hundreds of dollars in hours. Most teams discover this **on the invoice**, not in real time.

Existing solutions either:
- Lock you into a specific proxy/gateway vendor
- Require heavyweight observability platforms (Datadog, Helicone, etc.)
- Only show aggregate spend — not *who* or *what* is driving it

**Token Burn solves this differently.** It embeds directly into your Python backend as a LiteLLM callback — zero infrastructure beyond a Postgres container. Every LLM call is automatically logged with user attribution, feature tagging, and precise cost calculation. dbt transforms the raw logs into a burn-rate model that projects daily spend, and a Python watchdog flags budget breaches before they hit your wallet.

### Who Is This For?

- **Solo devs / small teams** shipping LLM features who need cost visibility without a $500/mo observability platform
- **Data/ML engineers** who want to demonstrate FinOps proficiency with real, production-grade patterns
- **Backend teams** integrating LLMs into existing Python services (FastAPI, Django, etc.) who need cost attribution per user or feature
- **Anyone** who's been surprised by an LLM invoice and wants it to never happen again

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Your Python Backend                                │
│                                                     │
│  app code ──▶ llm_client.completion()               │
│                    │                                 │
│                    ▼                                 │
│              LiteLLM SDK ──▶ OpenAI / Anthropic     │
│                    │                                 │
│                    ▼  (success_callback)             │
│              spend_logger.log_spend()                │
│                    │  async                          │
│                    ▼                                 │
│              asyncpg ──▶ PostgreSQL                  │
│                          raw_spend_logs              │
└─────────────────────────────────────────────────────┘
                           │
                    dbt run │
                           ▼
                    daily_burn_summary (view)
                           │
                    python  │  watchdog.py
                           ▼
                    CRITICAL BUDGET ALERT (stdout)
```

**No proxy server. No sidecar.** The callback lives inside your process. LiteLLM fires it after every successful completion. The callback extracts usage, calculates cost from a local rate card, and does an async insert via `asyncpg` — non-blocking, so it never adds latency to your LLM responses.

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **LiteLLM SDK callback** (not proxy) | Embeds into any existing Python backend. No extra container, no network hop, no port management. |
| **asyncpg** | Fastest Python Postgres driver. Non-blocking inserts don't stall the LLM response path. |
| **Local rate card** (`rates.py`) | Deterministic, auditable cost calculation. No dependency on external pricing APIs. Update one file when providers change pricing. |
| **`ON CONFLICT DO NOTHING`** | Idempotent inserts keyed on `request_id`. Safe retries, safe replays, no duplicate cost attribution. |
| **JSONB metadata column** | Store arbitrary context (`team`, `environment`, `experiment_id`) without schema migrations. |
| **dbt views** (not tables) | Always-fresh at MVP scale — no scheduler needed. Switch to `incremental` when logs exceed ~1M rows. |
| **Burn rate = cost / active_hours × 24** | More predictive than raw daily totals. Catches acceleration early in the day — a user who spent $5 in 2 hours is on track for $60/day. |
| **Watchdog exit code 1 on breach** | Composable with cron, CI gates, or any process supervisor. |

---

## Project Structure

```
LLM-Token-Monitor/
├── docker-compose.yml          # Postgres 16 container
├── .env                        # API keys & DB credentials (git-ignored)
├── .gitignore
├── requirements.txt            # Python dependencies
├── example.py                  # Smoke-test: 3 LLM calls through the pipeline
├── seed_test_data.py           # Synthetic data loader for testing without API keys
│
├── sql/
│   └── create_tables.sql       # DDL for raw_spend_logs (auto-runs on first boot)
│
├── src/
│   ├── __init__.py
│   ├── config.py               # Environment variable loading
│   ├── db.py                   # asyncpg connection pool management
│   ├── rates.py                # Cost-per-token rate card
│   ├── spend_logger.py         # LiteLLM success callback (core pipeline)
│   ├── llm_client.py           # Wrapped completion() with auto-logging
│   └── watchdog.py             # Budget-breach scanner
│
└── dbt/
    ├── dbt_project.yml
    ├── profiles.yml
    └── models/
        ├── staging/
        │   ├── sources.yml
        │   └── stg_spend_logs.sql      # Cleaned/normalized raw logs
        └── marts/
            └── daily_burn_summary.sql  # Burn rate + projected daily cost per user
```

---

## Quickstart

### Prerequisites

- **Docker Desktop** — running
- **Python 3.12+** — installed
- **One LLM API key** — OpenAI or Anthropic (only needed for live calls; synthetic data works without one)

### Setup

```bash
# 1. Clone the repo
git clone <your-repo-url> && cd LLM-Token-Monitor

# 2. Configure secrets
cp .env.example .env
# Edit .env — add your API key and set a Postgres password

# 3. Start Postgres (auto-creates the schema)
docker-compose up -d

# 4. Install Python deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 5. Build dbt views
cd dbt && dbt run --profiles-dir . && cd ..

# 6. Seed synthetic data (optional — test without an API key)
python seed_test_data.py

# 7. Run the watchdog
python -m src.watchdog
```

### Live API Calls

```python
from src.llm_client import completion

response = await completion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Summarise this document."}],
    user_id="alice",
    feature_name="summariser",
)
# That's it — spend is logged automatically.
```

---

## How Each Component Works

### 1. Spend Logger (`src/spend_logger.py`)

The callback registered on `litellm.success_callback`. After every successful LLM call:

1. Extracts `usage.prompt_tokens` and `usage.completion_tokens` from the response
2. Looks up the model in the local rate card (`rates.py`)
3. Calculates `cost = (prompt_tokens × prompt_rate) + (completion_tokens × completion_rate)`
4. Async-inserts a row into `raw_spend_logs` via `asyncpg`

The insert is fire-and-forget (`loop.create_task`) — it never blocks the caller. Failures are logged, never raised.

### 2. Raw Spend Logs (`sql/create_tables.sql`)

Append-only table optimised for high-write throughput:

- `BIGINT GENERATED ALWAYS AS IDENTITY` PK — faster than UUID PKs
- `UNIQUE INDEX on request_id` — idempotent dedup
- `JSONB metadata` — flexible sidecar for arbitrary dimensions
- Composite indexes on `(user_id, created_at)` and `(created_at)` for the aggregation queries dbt and the watchdog run

### 3. dbt Models

**`stg_spend_logs`** — Staging view that cleans/normalises the raw table (coalesces nulls, renames columns).

**`daily_burn_summary`** — Mart view that aggregates per user per day:

| Column | Description |
|---|---|
| `request_count` | Total LLM calls |
| `total_tokens` | Sum of all tokens |
| `total_cost_usd` | Sum of calculated cost |
| `active_hours` | Time span from first to last request (min 1hr) |
| `burn_rate_per_hour` | `total_cost / active_hours` |
| `projected_daily_cost` | `burn_rate × 24` — the watchdog threshold metric |

### 4. Watchdog (`src/watchdog.py`)

Queries `daily_burn_summary` for today's data. Any user whose `projected_daily_cost` exceeds the configured threshold (`DAILY_BUDGET_LIMIT_USD`, default $50) triggers a formatted `CRITICAL BUDGET ALERT` on stdout.

Returns exit code `1` on breach — plug into cron or CI:

```bash
# Run every 15 minutes via cron
*/15 * * * * cd /path/to/project && .venv/bin/python -m src.watchdog >> /var/log/token_burn.log 2>&1
```

---

## Example Output

```
  Found 1 user(s) exceeding budget threshold:

============================================================
  *** CRITICAL BUDGET ALERT ***
============================================================
  User ID            : heavy_spender
  Date               : 2026-03-12
  Spend So Far       : $1.1276
  Active Hours       : 2.0
  Burn Rate ($/hr)   : $0.5638
  Projected 24h Cost : $13.53
  Budget Limit       : $10.00
============================================================
```

---

## Configuration

All configuration is via environment variables in `.env`:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | — | Postgres connection string |
| `POSTGRES_PASSWORD` | `changeme` | Postgres password (used by Docker) |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `DAILY_BUDGET_LIMIT_USD` | `50.0` | Watchdog alert threshold (projected $/day) |

---

## Extending This

This is deliberately an MVP. Here's the natural evolution path:

| Next Step | Effort | How |
|---|---|---|
| **Per-user budget limits** | Low | Add a `dim_budgets` dbt seed CSV, join in the mart model |
| **Slack/Discord alerts** | Low | Add a webhook call in `watchdog.py` when breaches are found |
| **Grafana dashboard** | Medium | Point Grafana at Postgres, query `daily_burn_summary` |
| **Incremental dbt models** | Medium | Switch materialization to `incremental` with `created_at` partitioning |
| **Hard rate limiting** | Medium | Add a pre-call check in `llm_client.py` that queries current spend before allowing the LLM call |
| **Multi-provider rate cards** | Low | Extend `rates.py` with Anthropic, Gemini, Mistral pricing |
| **Scheduled dbt + watchdog** | Medium | Add Airflow/Dagster DAG or a simple cron job |

---

## Tech Stack

- **Python 3.12+** — Core language
- **LiteLLM** — Unified LLM SDK with callback hooks
- **asyncpg** — High-performance async Postgres driver
- **PostgreSQL 16** — Battle-tested OLTP database (runs in Docker)
- **dbt Core** — SQL transformation layer for cost modeling
- **Docker Compose** — Zero-install database provisioning

---

## License

MIT

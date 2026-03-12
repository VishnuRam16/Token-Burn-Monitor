"""
Insert synthetic spend rows to validate the full pipeline
without needing a live API key.

Run:  python seed_test_data.py
"""

import asyncio
import uuid
import random
from datetime import datetime, timezone, timedelta

import asyncpg
from src.config import DATABASE_URL

INSERT_SQL = """
    INSERT INTO raw_spend_logs
        (request_id, user_id, feature_name, model, provider,
         prompt_tokens, completion_tokens, total_tokens,
         cost_usd, latency_ms, metadata, created_at)
    VALUES
        ($1, $2, $3, $4, $5,
         $6, $7, $8,
         $9, $10, $11::jsonb, $12)
    ON CONFLICT (request_id) DO NOTHING;
"""

USERS = ["alice", "bob", "charlie", "diana"]
FEATURES = ["chat", "search", "summariser", "onboarding"]
MODELS = [
    ("gpt-4o-mini",  "openai",    0.15e-6, 0.60e-6),
    ("gpt-4o",       "openai",    2.50e-6, 10.00e-6),
]


async def seed():
    conn = await asyncpg.connect(dsn=DATABASE_URL)
    now = datetime.now(timezone.utc)
    inserted = 0

    try:
        for user in USERS:
            # Give each user a different usage intensity
            num_calls = random.randint(5, 30)
            for i in range(num_calls):
                model_name, provider, prompt_rate, comp_rate = random.choice(MODELS)
                prompt_tok = random.randint(50, 2000)
                comp_tok = random.randint(20, 1500)
                total_tok = prompt_tok + comp_tok
                cost = (prompt_tok * prompt_rate) + (comp_tok * comp_rate)

                # Spread requests across the last few hours
                offset = timedelta(minutes=random.randint(0, 360))
                ts = now - offset

                import json
                md = json.dumps({"user_id": user, "feature_name": random.choice(FEATURES)})

                await conn.execute(
                    INSERT_SQL,
                    uuid.uuid4(),
                    user,
                    random.choice(FEATURES),
                    model_name,
                    provider,
                    prompt_tok,
                    comp_tok,
                    total_tok,
                    cost,
                    random.randint(200, 3000),
                    md,
                    ts,
                )
                inserted += 1

        # Also add a "heavy spender" to trigger the watchdog
        for i in range(50):
            prompt_tok = random.randint(1000, 4000)
            comp_tok = random.randint(500, 3000)
            cost = (prompt_tok * 2.50e-6) + (comp_tok * 10.00e-6)
            offset = timedelta(minutes=random.randint(0, 120))
            ts = now - offset

            import json
            md = json.dumps({"user_id": "heavy_spender", "feature_name": "bulk_analysis"})

            await conn.execute(
                INSERT_SQL,
                uuid.uuid4(),
                "heavy_spender",
                "bulk_analysis",
                "gpt-4o",
                "openai",
                prompt_tok,
                comp_tok,
                prompt_tok + comp_tok,
                cost,
                random.randint(500, 5000),
                md,
                ts,
            )
            inserted += 1

        print(f"Inserted {inserted} synthetic rows into raw_spend_logs.")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())

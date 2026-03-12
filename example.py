"""Quick smoke-test: make a few calls and verify logs land in Postgres."""

import asyncio
from src.llm_client import completion
from src.db import close_pool, get_pool


async def main():
    # --- 1. Make LLM calls as different users / features ---
    print("[1/3] Calling gpt-4o-mini as user 'alice' (onboarding)...")
    r1 = await completion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say hello in three words."}],
        user_id="alice",
        feature_name="onboarding",
    )
    print(f"  → {r1.choices[0].message.content}\n")

    print("[2/3] Calling gpt-4o-mini as user 'bob' (search)...")
    r2 = await completion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "What is 2+2?"}],
        user_id="bob",
        feature_name="search",
    )
    print(f"  → {r2.choices[0].message.content}\n")

    print("[3/3] Calling gpt-4o-mini as user 'alice' (chat)...")
    r3 = await completion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Tell me a one-line joke."}],
        user_id="alice",
        feature_name="chat",
    )
    print(f"  → {r3.choices[0].message.content}\n")

    # Give background logger tasks time to flush
    await asyncio.sleep(2)

    # --- 2. Verify rows landed ---
    pool = await get_pool()
    rows = await pool.fetch("SELECT user_id, model, cost_usd, prompt_tokens, completion_tokens FROM raw_spend_logs ORDER BY created_at DESC LIMIT 5")
    print(f"{'=' * 60}")
    print(f"  raw_spend_logs — {len(rows)} row(s) found")
    print(f"{'=' * 60}")
    for r in rows:
        print(f"  user={r['user_id']:>8}  model={r['model']:<16}  cost=${float(r['cost_usd']):.6f}  tokens={r['prompt_tokens']}+{r['completion_tokens']}")
    print()

    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())

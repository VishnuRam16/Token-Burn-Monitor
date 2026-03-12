"""
Watchdog: queries the dbt daily_burn_summary and prints alerts
for any user whose burn rate projects to exceed the daily budget.

Run:  python -m src.watchdog
"""

import asyncio
import sys

import asyncpg

from src.config import DATABASE_URL, DAILY_BUDGET_LIMIT_USD

ALERT_QUERY = """
    select
        user_id,
        spend_date,
        total_cost_usd,
        active_hours,
        burn_rate_per_hour,
        projected_daily_cost
    from daily_burn_summary
    where spend_date = current_date
      and projected_daily_cost > $1
    order by projected_daily_cost desc;
"""


def _format_alert(row: asyncpg.Record) -> str:
    return (
        f"\n{'=' * 60}\n"
        f"  *** CRITICAL BUDGET ALERT ***\n"
        f"{'=' * 60}\n"
        f"  User ID            : {row['user_id']}\n"
        f"  Date               : {row['spend_date']}\n"
        f"  Spend So Far       : ${row['total_cost_usd']:.4f}\n"
        f"  Active Hours       : {row['active_hours']:.1f}\n"
        f"  Burn Rate ($/hr)   : ${row['burn_rate_per_hour']:.4f}\n"
        f"  Projected 24h Cost : ${row['projected_daily_cost']:.2f}\n"
        f"  Budget Limit       : ${DAILY_BUDGET_LIMIT_USD:.2f}\n"
        f"{'=' * 60}\n"
    )


async def run_watchdog() -> int:
    conn = await asyncpg.connect(dsn=DATABASE_URL)
    try:
        rows = await conn.fetch(ALERT_QUERY, DAILY_BUDGET_LIMIT_USD)
        if not rows:
            print(f"[OK] No users projecting above ${DAILY_BUDGET_LIMIT_USD:.2f}/day.")
            return 0

        print(f"\n  Found {len(rows)} user(s) exceeding budget threshold:\n")
        for row in rows:
            print(_format_alert(row))
        return 1
    finally:
        await conn.close()


def main() -> None:
    exit_code = asyncio.run(run_watchdog())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

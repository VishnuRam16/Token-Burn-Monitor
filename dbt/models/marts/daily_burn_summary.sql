/*
    Daily burn summary per user.

    Key metric — burn_rate_per_hour:
      total_cost / hours_active_today

    If a user spent $5 across 2 hours of activity, their burn rate
    is $2.50/hr → projected daily = $60.  That triggers the watchdog.
*/

with activity as (

    select
        user_id,
        date(created_at)                                    as spend_date,

        count(*)                                            as request_count,
        sum(prompt_tokens)                                  as total_prompt_tokens,
        sum(completion_tokens)                              as total_completion_tokens,
        sum(total_tokens)                                   as total_tokens,
        sum(cost_usd)                                       as total_cost_usd,

        -- hours between first and last request today (min 1 to avoid div-by-zero)
        greatest(
            extract(epoch from max(created_at) - min(created_at)) / 3600.0,
            1.0
        )                                                   as active_hours,

        avg(latency_ms)                                     as avg_latency_ms

    from {{ ref('stg_spend_logs') }}
    group by user_id, date(created_at)

),

burn as (

    select
        *,
        total_cost_usd / active_hours                       as burn_rate_per_hour,
        (total_cost_usd / active_hours) * 24                as projected_daily_cost
    from activity

)

select * from burn

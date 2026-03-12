with source as (

    select * from {{ source('app', 'raw_spend_logs') }}

),

cleaned as (

    select
        id,
        request_id,
        created_at,
        user_id,
        coalesce(feature_name, 'untagged')  as feature_name,
        model,
        provider,
        prompt_tokens,
        completion_tokens,
        total_tokens,
        cost_usd,
        latency_ms,
        metadata
    from source

)

select * from cleaned

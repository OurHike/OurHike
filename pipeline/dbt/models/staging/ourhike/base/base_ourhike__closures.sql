-- OurHike's moderator-verified closures (extract/_shared/ourhike/closures.py,
-- export_conditions.py's PUBLIC_CLOSURES_SQL run whole), keyed (decision
-- 40), with nothing filtered: the query's own `moderation_status =
-- 'verified'` is the gate (gate 4), and int_closures__ourhike_checked checks
-- it again. Every column is the query's, so conditions/closures.json's
-- writer can print each one as today. The times are TIMESTAMPTZ, UTC: the
-- columns are `timestamp without time zone` holding UTC (app/core/time.py),
-- and dlt reads a naive time as UTC.
--
-- Key: the closure's UUID primary key.
with source as (
    select * from {{ source('ourhike', 'raw_ourhike__closures') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'ourhike_closures'",
            'id',
        ]) }} as ourhike_closure_key,
        id as closure_uuid,
        reported_at,
        trail_id,
        start_mile_marker,
        end_mile_marker,
        reason_type,
        note,
        status as closure_status,
        moderation_status,
        verified_at,
        closed_since,
        expected_reopen,
        reroute_url,
        start_lat,
        start_lon,
        end_lat,
        end_lon,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='ourhike_closure_key', order_by='_dlt_id'
) }}

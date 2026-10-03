{{ config(
    format='json',
    location='conditions_closures.json',
    meta={'when_empty': 'keep_last_file', 'gate': 'ourhike_closures'},
) }}
-- conditions/closures.json, OurHike's moderator-verified closures, in the
-- shape export_conditions.py's build_document("closures", ...) writes:
-- `generated_at` and every row PUBLIC_CLOSURES_SQL selects, in its order
-- (start_mile_marker, id), its timestamps stamped by _stamp_utc().
--
-- WHICH ROWS: OurHike's closures in both marts. `closed` and
-- `reroute_available` block the trail and are in the closures mart; `open`,
-- and a status the backend does not define, are in the warnings mart
-- (int_closures__ourhike_checked says why), and the file has always held
-- every verified closure whatever its status: the client reads `status`.
--
-- NO ROW, SO NO FILE, while int_closures__gate holds OurHike's closures back
-- (`meta.gate`): for a row, a number that is not finite, or because
-- int_sources__publication does. The phone keeps its last file, and
-- publish.py fails the run after publishing the rest.
--
-- `generated_at` is dbt's run_started_at: one clock for this file and
-- conditions/reports.json, as export_conditions.py's main() keeps one.
with ourhike_rows as (
    select
        closure_uuid,
        reported_at,
        trail_id,
        mile_start,
        mile_end,
        reason_type,
        note,
        closure_status,
        moderation_status,
        verified_at,
        closed_since,
        expected_reopen,
        reroute_url,
        start_lat,
        start_lon,
        end_lat,
        end_lon
    from {{ ref('closures', v=1) }}
    where source_key = 'ourhike_closures'
    union all
    select
        closure_uuid,
        reported_at,
        trail_id,
        mile_start,
        mile_end,
        reason_type,
        note,
        closure_status,
        moderation_status,
        verified_at,
        closed_since,
        expected_reopen,
        reroute_url,
        start_lat,
        start_lon,
        end_lat,
        end_lon
    from {{ ref('warnings', v=1) }}
    where source_key = 'ourhike_closures' and warning_kind = 'org_notice'
),

gate as (
    select * from {{ ref('int_closures__gate') }}
    where source_key = 'ourhike_closures'
),

published as (
    select
        coalesce(
            list(
                json_object(
                    'id', closure_uuid,
                    'reported_at', {{ python_utc_isoformat('reported_at') }},
                    'trail_id', trail_id,
                    'start_mile_marker', mile_start,
                    'end_mile_marker', mile_end,
                    'reason_type', reason_type,
                    'note', note,
                    'status', closure_status,
                    'moderation_status', moderation_status,
                    'verified_at', {{ python_utc_isoformat('verified_at') }},
                    'closed_since', {{ python_utc_isoformat('closed_since') }},
                    'expected_reopen',
                    {{ python_utc_isoformat('expected_reopen') }},
                    'reroute_url', reroute_url,
                    'start_lat', start_lat,
                    'start_lon', start_lon,
                    'end_lat', end_lat,
                    'end_lon', end_lon
                ) order by mile_start, closure_uuid
            ),
            []
        ) as closures
    from ourhike_rows
)

select
    {{ python_run_stamp() }} as generated_at,
    published.closures
from published
inner join gate on gate.source_key = 'ourhike_closures'
where gate.passed

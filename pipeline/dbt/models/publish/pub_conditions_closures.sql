{{ config(format='json', location='conditions_closures.json') }}
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
-- NOTHING IS WRITTEN, and the phone keeps its last good file, when
-- int_closures__gate holds OurHike's closures back (for a row, or because
-- int_sources__publication does), or when a row carries a mile or a
-- coordinate that is not a finite
-- number: write_document()'s allow_nan=False, because JSON.parse on a phone
-- rejects the whole document on one NaN (lib/strict_json.py, #658).
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
    from {{ ref('closures') }}
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
    from {{ ref('warnings') }}
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
        ) as closures,
        count(*) filter (
            where not (
                coalesce(isfinite(mile_start), true)
                and coalesce(isfinite(mile_end), true)
                and coalesce(isfinite(start_lat), true)
                and coalesce(isfinite(start_lon), true)
                and coalesce(isfinite(end_lat), true)
                and coalesce(isfinite(end_lon), true)
            )
        ) as rows_not_finite
    from ourhike_rows
),

judged as (
    select
        published.closures,
        published.rows_not_finite,
        coalesce(gate.passed, false) as passed,
        coalesce(
            gate.held_because,
            'int_closures__gate has no row for ourhike_closures'
        ) as held_because
    from published
    left join gate on true
)

select
    case
        when passed and rows_not_finite = 0
            then {{ python_run_stamp() }}
        when not passed
            then error(
                'conditions/closures.json is not written: ' || held_because
            )
        else error(
            'conditions/closures.json is not written: ' || rows_not_finite
            || ' row(s) carry a mile or a coordinate that is not a finite '
            || 'number, and JSON.parse on a phone rejects the whole document'
        )
    end as generated_at,
    closures
from judged

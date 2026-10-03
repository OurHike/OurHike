-- OurHike's moderator-verified closures (base_ourhike__closures), one row
-- each, with whether each blocks the trail and why one cannot publish.
--
-- WHICH ONES BLOCK THE TRAIL is the closure's own status, read as the phone
-- reads it: client/src/lib/closureBanner.ts says "A reopened closure is not
-- a warning. A reroute is - having somewhere else to walk does not make the
-- trail itself passable". So `closed` and `reroute_available` obstruct, and
-- `open` does not and lands in the warnings mart (decision 7). A status the
-- backend does not define (app/models/closure.py's ClosureStatus) is not
-- classified, and lands there too, as unknown.
--
-- THE MODERATION GATE IS CHECKED AGAIN (CL15, gate 4): the extract's query
-- already selects `moderation_status = 'verified'` only, and a row that is
-- not is a problem here, so a query edited to let others through holds back
-- OurHike's closures rather than publishing them. `verified_by` and
-- `reported_by` never left the database (_kinds.py's WITHHELD_COLUMNS).
--
-- A MILE OR COORDINATE THAT IS NOT A FINITE NUMBER is a problem too:
-- export_conditions.py's write_document() refuses it (allow_nan=False),
-- because JSON.parse on a phone rejects the whole document over one NaN
-- (lib/strict_json.py, #658). The backend bounds a closure's miles itself
-- (app/schemas/closure.py, #257), so this is the second lock. Nothing else is
-- refused: the closures mart's tests report a mile outside the A.T.'s
-- 0.5-2197.5 at warn rather than hold OurHike's closures back over one.
with closures as (
    select * from {{ ref('base_ourhike__closures') }}
),

checked as (
    select
        *,
        case
            when closure_status in ('closed', 'reroute_available') then true
            when closure_status = 'open' then false
        end as obstructs_trail,
        list_filter(
            [
                case
                    when
                        moderation_status != 'verified'
                        or moderation_status is null
                        then
                            closure_uuid || ': moderation_status is '
                            || coalesce(moderation_status, 'null')
                            || ', and only a verified closure leaves the '
                            || 'database'
                end,
                case
                    when
                        not (
                            coalesce(isfinite(start_mile_marker), true)
                            and coalesce(isfinite(end_mile_marker), true)
                            and coalesce(isfinite(start_lat), true)
                            and coalesce(isfinite(start_lon), true)
                            and coalesce(isfinite(end_lat), true)
                            and coalesce(isfinite(end_lon), true)
                        )
                        then
                            closure_uuid
                            || ': a mile or a coordinate is not '
                            || 'a finite number, and JSON.parse on a phone '
                            || 'rejects the whole document'
                end
            ],
            lambda p: p is not null
        ) as problems
    from closures
)

select
    ourhike_closure_key,
    closure_uuid,
    reported_at,
    trail_id,
    start_mile_marker,
    end_mile_marker,
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
    end_lon,
    obstructs_trail,
    problems,
    nullif(array_to_string(problems, ' | '), '') as problem,
    _loaded_at
from checked

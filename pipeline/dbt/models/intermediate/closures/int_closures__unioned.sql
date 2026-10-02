-- Every notice, area and closure the closures and warnings marts are split
-- from (pipeline/ELT.md, "The eleven marts"), one row each, by name: ATC's
-- reviewed Trail Updates, NYNJTC's Trail Alerts, NYS Parks' temporary closed
-- areas and OurHike's own verified closures. Nothing is filtered here. Each
-- branch keeps its source's own words and adds what the split needs:
--
--   obstructs_trail  whether a hiker is stopped from walking through, as the
--                    source says: ATC's reviewed boolean; true for a closed
--                    area; OurHike's status read as closureBanner.ts reads it;
--                    NULL for every NYNJTC alert, which nobody has classified
--                    (decision 7: unknown lands in warnings, never dropped).
--   review_state     who stands behind it: `reviewed` (a person read ATC's
--                    page), `org_published` (NYS Parks' own layer),
--                    `moderator_verified` (OurHike's moderators),
--                    `not_reviewed` (NYNJTC, unread by anyone here).
--   problems         why a row cannot publish, from its source's checks;
--                    int_closures__gate holds back a source with any.
--
-- `notice_id` is `<source key>:<the source's own id>` (features/ORG_NOTICES.md
-- §2, the form nynjtc_alerts.json already publishes), and the marts' keys are
-- it. A row whose own id is missing or repeated is named by its place in the
-- source instead, so the id stays unique while the gate holds that source back.
--
-- Miles are A.T. miles from Springer, ATC's and OurHike's, and null for a
-- notice nobody has placed. Dates are each source's own and null where it
-- gives none: NYS Parks publishes none, and none is invented (CL13).
with atc as (
    select * from {{ ref('int_closures__atc_checked') }}
),

nynjtc as (
    select * from {{ ref('int_closures__nynjtc_checked') }}
),

oprhp as (
    select * from {{ ref('int_closures__oprhp_areas') }}
),

ourhike as (
    select * from {{ ref('int_closures__ourhike_checked') }}
)

-- `union all by name` matches the branches' columns by name, and a branch
-- leaves out what its source does not have, which reads as null. SQLFluff
-- 4.3.0 counts the columns as if the union were positional (AM07), so that
-- rule is told not to here.
select  -- noqa: AM07
    case
        when
            coalesce(atc_id, '') != ''
            and row_number() over (partition by atc_id order by file_row) = 1
            then 'atc_trail_updates:' || atc_id
        else 'atc_trail_updates:row-' || file_row
    end as notice_id,
    atc_update_row_key as source_row_key,
    'atc_trail_update' as notice_kind,
    'atc' as club,
    'atc_trail_updates' as source_key,
    obstructs_trail,
    'reviewed' as review_state,
    atc_id,
    title,
    category,
    states,
    'AT' as trail_id,
    cast(start_mile_text as double) as mile_start,
    cast(end_mile_text as double) as mile_end,
    try_cast(updated_at as timestamptz) as source_edited_at,
    updated_at,
    source_url,
    file_row as list_position,
    problems,
    _loaded_at
from atc

union all by name

select
    notice_id,
    trail_alert_key as source_row_key,
    'nynjtc_trail_alert' as notice_kind,
    'nynjtc' as club,
    'nynjtc_trail_alerts' as source_key,
    cast(null as boolean) as obstructs_trail,
    'not_reviewed' as review_state,
    title,
    locality,
    modified_at as source_edited_at,
    updated_at,
    source_url,
    problems,
    _loaded_at
from nynjtc

union all by name

select
    'oprhp_trail_closures:' || closure_key as notice_id,
    closure_key as source_row_key,
    'oprhp_closure_area' as notice_kind,
    'nysparks' as club,
    'oprhp_trail_closures' as source_key,
    true as obstructs_trail,
    'org_published' as review_state,
    'area' as closure_kind,
    closure_reason,
    closure_place,
    geom_geojson,
    cast([] as varchar[]) as problems,
    _loaded_at
from oprhp

union all by name

select
    'ourhike_closures:' || closure_uuid as notice_id,
    ourhike_closure_key as source_row_key,
    'ourhike_closure' as notice_kind,
    'ourhike' as club,
    'ourhike_closures' as source_key,
    obstructs_trail,
    'moderator_verified' as review_state,
    closure_uuid,
    trail_id,
    start_mile_marker as mile_start,
    end_mile_marker as mile_end,
    reported_at,
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
    problems,
    _loaded_at
from ourhike

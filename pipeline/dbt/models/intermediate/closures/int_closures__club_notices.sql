{{ config(materialized='table') }}
-- Every generated club notice source's rows
-- (int_closures__club_notices_unioned, pipeline/generate_notice_models.py),
-- read by decision 53's phase C rules
-- (pipeline/ELT.md, "Every club's closures and alerts", phase C): one row per
-- notice, in the closures family's columns, with whether it blocks the trail
-- and, where it may not publish as current, why. Nothing is dropped here; the
-- finals leave out a row whose `held_because` is set, so the reason stays
-- readable in the warehouse.
--
-- THE RULES, each held by a unit test in _closures__intermediate.yml:
--
-- 1. A NOTICE WHOSE STATED END HAS PASSED IS HELD BACK WITH THAT REASON, never
--    published as current (Standing Stone's closure pages still serve
--    closures that ended in 2022 and 2023, phase A). Its end is the day of
--    `ends_at` in UTC, and it is held once that day is more than one day
--    behind the build's UTC date: a day stated in a club's own zone has ended
--    everywhere in the United States, UTC-4 to UTC-10, by 10:00 UTC the day
--    after, so the margin errs toward showing a closure a day too long and
--    never hides one early (Reasoned, not measured on any source). An order
--    the source says was rescinded on a day already reached is held too.
-- 2. A STATUS ALONE IS NEVER READ AS CLOSED NOW WHEN ITS OWN END HAS PASSED.
--    `obstructs_trail` is true only where the source's own status field
--    holds a value seeds/notice_status_values.csv reads as `closes_trail`,
--    the source files the notice under closures (its club's closures.py),
--    and rule 1 does not hold it: the USFS R06 fire closures carried
--    'Active' beside an end date already past on 112 of 938 lines, and CDPR
--    'Full Closure' beside a passed StatusReopenDate is the same shape
--    (pipeline/ELT.md, "Status, water and expiry rules", rule 1).
--    Everything else is null, which decision 7 lands in warnings as not
--    reviewed: miss rather than cry wolf.
-- 3. A STATUS THE SOURCE USES FOR "NOT CURRENT" HOLDS THE ROW: an inactive
--    flag (CDTC's Active No, Wisconsin DNR's Active_Flag No), an unposted
--    one (IATA's posted no), or an open one, which tells a hiker nothing.
-- 4. PLACE ONLY FROM THE SOURCE'S OWN GEOMETRY. `geom_geojson` is the
--    staging model's own geometry, never a match of `locality` or a title
--    against a place table: a notice with none is unplaced, and its
--    locality is the source's own words for where (ORG_NOTICES.md section
--    3). A reviewed term table, the other way phase C allows, does not
--    exist for any of these sources yet.
-- 5. FACTS AND A LINK (decision 55). The columns are the notice's title,
--    category, dates, place and link; no prose column exists to carry, and
--    int_warnings__wording_leaks fails the build if one reaches a mart.
--
-- `updated_at` is the source's own edit stamp, in ISO 8601 UTC, and null
-- where it gives none: never the load time. `notice_id` is
-- `<source key>:<the source's own id>` (features/ORG_NOTICES.md section 2).
with notices as (
    select * from {{ ref('int_closures__club_notices_unioned') }}
),

status_values as (
    select * from {{ ref('notice_status_values') }}
),

read_status as (
    select
        notices.*,
        status_values.reads_as as status_reads,
        cast(timezone('UTC', notices.ends_at) as date) as ends_on,
        cast(timezone('UTC', notices.rescinded_at) as date) as rescinded_on,
        cast(timezone('UTC', now()) as date) as build_date
    from notices
    left join status_values
        on
            notices.source_key = status_values.source_key
            and lower(trim(notices.status)) = lower(status_values.status_value)
),

judged as (
    select
        *,
        case
            when status_reads = 'not_current'
                then
                    'its own status reads ' || status
                    || ', which the source uses for a notice that is not '
                    || 'current'
            when rescinded_on is not null and rescinded_on <= build_date
                then 'its own order was rescinded on ' || rescinded_on
            when ends_on is not null and ends_on < build_date - 1
                then 'its own end date, ' || ends_on || ', has passed'
        end as held_because
    from read_status
)

select
    source_key || ':' || coalesce(source_id, 'key-' || notice_key) as notice_id,
    notice_key as source_row_key,
    'club_' || reader as notice_kind,
    club,
    source_key,
    notice_type,
    listing,
    case
        when
            notice_type = 'closures'
            and status_reads = 'closes_trail'
            and held_because is null
            then true
    end as obstructs_trail,
    case
        when
            notice_type = 'closures'
            and status_reads = 'closes_trail'
            and held_because is null
            then 'org_published'
        else 'not_reviewed'
    end as review_state,
    {{ python_html_unescape('title') }} as title,
    category,
    status,
    status_reads,
    locality,
    starts_at,
    ends_on,
    rescinded_on,
    source_edited_at,
    strftime(timezone('UTC', source_edited_at), '%Y-%m-%dT%H:%M:%SZ')
        as updated_at,
    source_url,
    geom_geojson,
    held_because,
    _loaded_at
from judged

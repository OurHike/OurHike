-- int_warnings__final: the warnings mart's rows before their row dates, every
-- contracted column but _first_seen_at and _changed_at. This is what
-- models/marts/warnings/warnings.sql held until decision 57;
-- int_warnings__history snapshots it, and the mart reads that snapshot.
--
-- What a hiker should know that does not block the trail (pipeline/ELT.md,
-- "The eleven marts", decision 2): organization notices that do not
-- obstruct it or that nobody has classified, NWS's relayed alerts, and
-- OurHike's serious reports. No hazard POIs: ELT.md's warnings ledger, "No
-- hazard POI exists to port". Every row's source may publish
-- (int_sources__publication), and a notice's source passed
-- int_closures__gate.
--
-- DECISION 7'S SPLIT, WARNINGS' HALF: every notice whose `obstructs_trail` is
-- false or null, never dropped. A null means nobody has classified it, so it
-- reads `not_reviewed` whatever its source says, and is never drawn as a
-- block. assert_every_notice_lands_in_exactly_one_of_closures_or_warnings
-- holds the partition.
--
-- EVERY CLUB'S WARNINGS-TYPE NOTICES too (int_warnings__unioned's club
-- branch, decision 53's phase C), through the same gate and publication
-- check as the notices above. A club notice whose own end date has passed,
-- or whose own status says it is not current, is left out, from either
-- branch.
--
-- REBUILT WHOLE EACH RUN, as int_closures__final is, so a lifted notice
-- leaves both, and both marts, in the same run.
--
-- A NOTICE SOURCE THE GATE HOLDS KEEPS ITS LAST GOOD ROWS, as
-- int_closures__final says (int_closures__held_carried, decision 53's phase
-- D). A closures-type club notice that does not close the trail lands here
-- with its own geometry, as a warnings-type one does, so a phone can place it.
with notices as (
    select * from {{ ref('int_closures__unioned') }}
),

gate as (
    select * from {{ ref('int_closures__gate') }}
),

others as (
    select * from {{ ref('int_warnings__unioned') }}
),

publication as (
    select * from {{ ref('int_sources__publication') }}
),

org_notices as (
    select
        notices.notice_id as warning_id,
        'org_notice' as warning_kind,
        notices.club,
        notices.source_key,
        notices._loaded_at,
        notices.notice_kind,
        notices.obstructs_trail,
        case
            when notices.obstructs_trail is null then 'not_reviewed'
            else notices.review_state
        end as review_state,
        notices.atc_id,
        notices.title,
        notices.category,
        notices.states,
        notices.locality,
        notices.trail_id,
        notices.mile_start,
        notices.mile_end,
        notices.starts_on,
        notices.ends_on,
        notices.source_edited_at,
        notices.updated_at,
        notices.source_url,
        notices.geom_geojson,
        notices.list_position,
        notices.closure_uuid,
        notices.reported_at,
        notices.reason_type,
        notices.note,
        notices.closure_status,
        notices.moderation_status,
        notices.verified_at,
        notices.closed_since,
        notices.expected_reopen,
        notices.reroute_url,
        notices.start_lat,
        notices.start_lon,
        notices.end_lat,
        notices.end_lon,
        notices.source_row_key,
        cast(null as timestamptz) as carried_since
    from notices
    inner join gate on notices.source_key = gate.source_key
    inner join publication on notices.source_key = publication.source_key
    where
        gate.passed
        and publication.may_publish
        and not coalesce(notices.obstructs_trail, false)
        and notices.notice_held_because is null
),

-- A feed's notices that aged out of its window, never lifted by absence
-- (int_closures__window_carried, decision 53's phase C).
carried as (
    select
        carried.notice_id as warning_id,
        'org_notice' as warning_kind,
        carried.club,
        carried.source_key,
        carried._loaded_at,
        carried.notice_kind,
        carried.obstructs_trail,
        carried.review_state,
        carried.title,
        carried.category,
        carried.locality,
        carried.source_edited_at,
        carried.updated_at,
        carried.source_url,
        carried.geom_geojson,
        carried.source_row_key
    from {{ ref('int_closures__window_carried') }} as carried
    inner join publication on carried.source_key = publication.source_key
    where carried.mart = 'warnings' and publication.may_publish
),

-- A notice source the gate holds keeps its last good rows
-- (int_closures__held_carried says which, and from when).
held_carried as (
    select
        held_carried.notice_id as warning_id,
        'org_notice' as warning_kind,
        held_carried.club,
        held_carried.source_key,
        held_carried._loaded_at,
        held_carried.notice_kind,
        held_carried.obstructs_trail,
        held_carried.review_state,
        held_carried.atc_id,
        held_carried.title,
        held_carried.category,
        held_carried.states,
        held_carried.locality,
        held_carried.trail_id,
        held_carried.mile_start,
        held_carried.mile_end,
        held_carried.starts_on,
        held_carried.ends_on,
        held_carried.source_edited_at,
        held_carried.updated_at,
        held_carried.source_url,
        held_carried.list_position,
        held_carried.geom_geojson,
        held_carried.source_row_key,
        held_carried.carried_since
    from {{ ref('int_closures__held_carried') }} as held_carried
    where held_carried.mart = 'warnings'
),

club_warnings as (
    select
        others.notice_id as warning_id,
        'org_notice' as warning_kind,
        others.club,
        others.source_key,
        others._loaded_at,
        others.notice_kind,
        others.obstructs_trail,
        case
            when others.obstructs_trail is null then 'not_reviewed'
            else others.review_state
        end as review_state,
        others.title,
        others.category,
        others.locality,
        others.starts_on,
        others.ends_on,
        others.source_edited_at,
        others.updated_at,
        others.source_url,
        others.geom_geojson,
        others.source_row_key
    from others
    inner join gate on others.source_key = gate.source_key
    inner join publication on others.source_key = publication.source_key
    where
        starts_with(others.notice_kind, 'club_')
        and gate.passed
        and publication.may_publish
        and others.notice_held_because is null
),

relayed as (
    select
        others.notice_id as warning_id,
        case
            when others.notice_kind = 'nws_alert' then 'nws_alert'
            else 'serious_report'
        end as warning_kind,
        others.club,
        others.source_key,
        others._loaded_at,
        others.notice_kind,
        others.obstructs_trail,
        others.review_state,
        others.source_edited_at,
        others.alert_id,
        others.alert_event,
        others.headline,
        others.alert_description,
        others.instruction,
        others.alert_severity,
        others.urgency,
        others.certainty,
        others.alert_response,
        others.message_type,
        others.sent_at,
        others.effective_at,
        others.onset_at,
        others.expires_at,
        others.ends_at,
        others.sender_name,
        others.area_desc,
        others.affected_zones,
        others.collection_updated,
        others.geom_geojson,
        others.report_uuid,
        others.report_type,
        others.poi_id,
        others.lat,
        others.lon,
        others.report_mile,
        others.reporter_type,
        others.reported_at,
        others.note,
        others.follow_up,
        others.report_status,
        others.visibility,
        others.report_severity,
        others.verified_at,
        others.source_row_key
    from others
    inner join publication on others.source_key = publication.source_key
    where
        publication.may_publish
        and not starts_with(others.notice_kind, 'club_')
)

-- `union all by name` matches the branches' columns by name, and a branch
-- leaves out what its source does not have, which reads as null. SQLFluff
-- 4.3.0 counts the columns as if the union were positional (AM07), so that
-- rule is told not to here.
select * from org_notices  -- noqa: AM07

union all by name

select * from relayed

union all by name

select * from club_warnings

union all by name

select * from carried

union all by name

select * from held_carried

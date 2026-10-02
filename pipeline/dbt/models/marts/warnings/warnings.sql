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
-- A TABLE, rebuilt whole each run, as the closures mart is, so a lifted
-- notice leaves both in the same run.
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
        notices.source_edited_at,
        notices.updated_at,
        notices.source_url,
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
        notices.source_row_key
    from notices
    inner join gate on notices.source_key = gate.source_key
    inner join publication on notices.source_key = publication.source_key
    where
        gate.passed
        and publication.may_publish
        and not coalesce(notices.obstructs_trail, false)
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
    where publication.may_publish
)

-- `union all by name` matches the branches' columns by name, and a branch
-- leaves out what its source does not have, which reads as null. SQLFluff
-- 4.3.0 counts the columns as if the union were positional (AM07), so that
-- rule is told not to here.
select * from org_notices  -- noqa: AM07

union all by name

select * from relayed

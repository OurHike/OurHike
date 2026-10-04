-- int_closures__final: the closures mart's rows before their row dates, every
-- contracted column but _first_seen_at and _changed_at. This is what
-- models/marts/closures/closures.sql held until decision 57;
-- int_closures__history snapshots it, and the mart reads that snapshot.
--
-- What blocks the trail, from every source that says so (pipeline/ELT.md,
-- "The eleven marts", decision 6): one row per notice, closed area or
-- closure that obstructs it, from a source that passed int_closures__gate
-- and may publish (int_sources__publication).
--
-- A CLUB NOTICE THAT MAY NOT PUBLISH AS CURRENT IS LEFT OUT: one whose own
-- end date has passed, or whose own status says it is not current
-- (int_closures__club_notices' `held_because`, decision 53's phase C).
--
-- DECISION 7'S SPLIT, CLOSURES' HALF: only rows whose `obstructs_trail` is
-- true. A null (nobody has classified it, every NYNJTC alert today) and a
-- false go to the warnings mart, never dropped, and the partition is held by
-- assert_every_notice_lands_in_exactly_one_of_closures_or_warnings.
--
-- REBUILT WHOLE EACH RUN: a lifted closure is not in its source's next
-- answer, so it leaves this model and int_warnings__final in the same run;
-- the snapshot then closes its version, and it leaves both marts.
--
-- The phone files read it with the warnings mart, because each of today's
-- files holds both halves of one source (pub_conditions_atc_updates,
-- pub_conditions_nynjtc_alerts, pub_conditions_closures).
with notices as (
    select * from {{ ref('int_closures__unioned') }}
),

gate as (
    select * from {{ ref('int_closures__gate') }}
),

publication as (
    select * from {{ ref('int_sources__publication') }}
),

-- A feed's notices that aged out of its window, never lifted by absence
-- (int_closures__window_carried, decision 53's phase C), through the same
-- publication check as every row.
carried as (
    select * from {{ ref('int_closures__window_carried') }}
    where mart = 'closures'
)

-- `union all by name` below: a carried row has the club notices' columns
-- only, and the rest read as null. SQLFluff 4.3.0 counts the columns as if
-- the union were positional (AM07), so that rule is told not to here.
select  -- noqa: AM07
    notices.notice_id as closure_id,
    notices.club,
    notices.source_key,
    notices._loaded_at,
    notices.notice_kind,
    notices.obstructs_trail,
    notices.review_state,
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
    notices.closure_kind,
    notices.closure_reason,
    notices.closure_place,
    notices.geom_geojson,
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
    and notices.obstructs_trail
    and notices.notice_held_because is null

union all by name

select
    carried.notice_id as closure_id,
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
from carried
inner join publication on carried.source_key = publication.source_key
where publication.may_publish

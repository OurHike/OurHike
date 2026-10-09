{{ config(materialized='table') }}
-- A NOTICE SOURCE THE GATE HOLDS KEEPS ITS LAST GOOD ROWS (decision 53, phase
-- D; pipeline/ELT.md, "Phase D: one notices file"): one row per notice the
-- previous build's row history held as current, of a source
-- int_closures__gate holds back this build, with every column the mart had,
-- in the mart it was in. int_closures__final and int_warnings__final add them
-- back, so a read that failed, a served copy this build could not add, or one
-- conflicting key never empties a club's notices from the marts or from
-- conditions/notices.json: the hiker keeps what OurHike last confirmed, and
-- `carried_since` says from when.
--
-- WHICH HOLDS CARRY. Every hold of a source the extract declares a notice
-- resource for (seeds/notice_readers.csv) and that int_sources__publication
-- lets publish. A source the registry holds back carries nothing: that hold
-- is a decision not to publish, never a failed read. OurHike's own closures
-- and reports, NWS's alerts and the work projects are not notice sources, so
-- none of them is carried; their writers keep the phone's last file instead,
-- as they always have. A feed's notice int_closures__window_carried carries
-- is left to it, so no notice is carried twice.
--
-- HOW LONG. A carried row stays in the mart, so the history keeps it current
-- and the next build carries it again, for as long as the source is held;
-- the first build that passes the source replaces every one with its fresh
-- rows. `carried_since` is the start of the first build that carried the row,
-- kept from the history after that, so it does not move while the hold lasts.
-- A row the history saved before this column existed reads it as absent and
-- takes this build's start. It is part of the row's content, so the row's
-- `_changed_at` moves when carrying starts and again when the source passes:
-- carried is a different claim from confirmed (Reasoned; macros/row_history.sql
-- says what else moves a hash).
--
-- WHAT ENDS IT EARLY: rule 1's dates (macros/notice_date_holds.sql), as for
-- a row read this build. A carried notice whose own end day is more than a
-- day behind the build's UTC date is dropped, so a closure its source says
-- has ended stops publishing although the source cannot be read; the
-- snapshot then closes its version. Only the end can pass while a row is
-- carried (its start was within the margin when it was read), and its
-- rescission day cannot be checked: rescinded_on does not reach the marts,
-- so the history holds none to carry.
-- And rule 7 (decision 128): a row of a source
-- seeds/notice_confirming_pages.csv names is carried only while its match
-- to an item on its page stands this build (int_closures__page_matches), so
-- a section whose item has left the page is dropped although its own layer
-- cannot be read, and so is one whose page this build cannot read either.
-- That rounds toward held, as int_closures__page_matches' header says why.
--
-- WHAT IT DOES NOT DO. With OURHIKE_ROW_HISTORY=off, or on a cold start, the
-- history is empty and nothing is carried, and so for a source held on every
-- build since its history began, which has no saved row to carry (review
-- finding DBT-10 of PR #1805 — dlt → dbt re-platform as one go/no-go
-- change, traced from macros/row_history.sql and
-- build_marts.resolve_history()). pub_conditions_notices then keeps the
-- phone's last file whole rather than publish such a club as having no
-- notices: with the history off while any notice source is held
-- (when_row_history_is_off()), and with it on while a source is held that
-- this build read rows of. A held source this build read no rows of, with
-- nothing to carry, is published as having none; that writer's header says
-- why.
with closures_history as (
    select
        'closures' as mart,
        closure_id as notice_id,
        source_key,
        row_json
    from {{ ref('stg_row_history__closures') }}
    where dbt_valid_to is null
),

warnings_history as (
    select
        'warnings' as mart,
        warning_id as notice_id,
        source_key,
        row_json
    from {{ ref('stg_row_history__warnings') }}
    where dbt_valid_to is null and warning_kind = 'org_notice'
),

saved as (
    select * from closures_history
    union all
    select * from warnings_history
),

gate as (
    select * from {{ ref('int_closures__gate') }}
),

notice_sources as (
    select distinct source_key
    from {{ ref('notice_readers') }}
),

window_carried as (
    select notice_id from {{ ref('int_closures__window_carried') }}
),

-- Rule 7's matches that stand this build; which sources confirm by page is
-- the gate's `confirms_by_page`.
standing_matches as (
    select
        notice_id,
        source_row_key
    from {{ ref('int_closures__page_matches') }}
    where held_because is null
),

carried as (
    select saved.*
    from saved
    inner join gate on saved.source_key = gate.source_key
    inner join notice_sources on saved.source_key = notice_sources.source_key
    left join window_carried on saved.notice_id = window_carried.notice_id
    left join standing_matches
        on
            saved.notice_id = standing_matches.notice_id
            and json_extract_string(saved.row_json, '$.source_row_key')
            = standing_matches.source_row_key
    where
        not gate.passed
        and gate.may_publish
        and window_carried.notice_id is null
        and (
            not coalesce(gate.confirms_by_page, false)
            or standing_matches.notice_id is not null
        )
),

read_back as (
    select
        mart,
        notice_id,
        json_extract_string(row_json, '$.club') as club,
        source_key,
        try_cast(json_extract_string(row_json, '$._loaded_at') as timestamptz)
            as _loaded_at,
        json_extract_string(row_json, '$.notice_kind') as notice_kind,
        try_cast(json_extract_string(row_json, '$.obstructs_trail') as boolean)
            as obstructs_trail,
        json_extract_string(row_json, '$.review_state') as review_state,
        json_extract_string(row_json, '$.atc_id') as atc_id,
        json_extract_string(row_json, '$.title') as title,
        json_extract_string(row_json, '$.category') as category,
        case
            when json_type(json_extract(row_json, '$.states')) not in ('NULL')
                then json_extract(row_json, '$.states')
        end as states,
        json_extract_string(row_json, '$.locality') as locality,
        json_extract_string(row_json, '$.trail_id') as trail_id,
        try_cast(json_extract_string(row_json, '$.mile_start') as double)
            as mile_start,
        try_cast(json_extract_string(row_json, '$.mile_end') as double)
            as mile_end,
        -- The two miles as the history saved them, for the unit test: a
        -- 2.0.6 unit test compares a double only after rounding it to one
        -- decimal place (the dbt skill's contract traps), and an A.T. mile is
        -- to a tenth.
        json_extract_string(row_json, '$.mile_start') as mile_start_text,
        json_extract_string(row_json, '$.mile_end') as mile_end_text,
        try_cast(json_extract_string(row_json, '$.starts_on') as date)
            as starts_on,
        try_cast(json_extract_string(row_json, '$.ends_on') as date) as ends_on,
        try_cast(
            json_extract_string(row_json, '$.source_edited_at') as timestamptz
        ) as source_edited_at,
        json_extract_string(row_json, '$.updated_at') as updated_at,
        json_extract_string(row_json, '$.source_url') as source_url,
        try_cast(json_extract_string(row_json, '$.list_position') as bigint)
            as list_position,
        json_extract_string(row_json, '$.closure_kind') as closure_kind,
        json_extract_string(row_json, '$.closure_reason') as closure_reason,
        json_extract_string(row_json, '$.closure_place') as closure_place,
        json_extract_string(row_json, '$.geom_geojson') as geom_geojson,
        json_extract_string(row_json, '$.source_row_key') as source_row_key,
        coalesce(
            try_cast(
                json_extract_string(row_json, '$.carried_since') as timestamptz
            ),
            cast({{ python_run_stamp() }} as timestamptz)
        ) as carried_since
    from carried
)

select *
from read_back
where
    case
        {{ notice_date_holds('starts_on', 'ends_on', notice_build_date()) }}
    end is null

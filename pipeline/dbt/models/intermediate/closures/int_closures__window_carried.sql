{{ config(materialized='table') }}
-- A FEED IS A WINDOW, NOT A LIST (phase C; measured by phase B's
-- FeedNotices, 2026-10-03: CFPA's feed carries 10 of its 30 notices). A
-- notice from a source whose answer is its newest items
-- (seeds/notice_readers.csv's `listing` = 'window') that the previous build's
-- closures or warnings mart held, and that this build's read no longer
-- carries, has aged out of the window, which says nothing about whether it
-- was lifted. So it is carried, with the content the mart last held, into
-- int_closures__final or int_warnings__final, and the snapshot
-- never closes it on absence alone.
--
-- IT STAYS UNTIL, per phase C:
-- - a person marks it lifted (seeds/notice_marks.csv);
-- - nothing about its own end date: a notice past it is kept, greyed on the
--   phone (the maintainer's choice, 2026-10-10). A feed item states no end
--   (extract/_notices.py's FEED_COLUMNS), but a closure that carries one
--   and has passed it is moved to the warnings mart and closes nothing, as
--   int_closures__held_carried does;
-- - the club's own full listing omits it: where a club publishes the full
--   list, that list is registered as the source and the feed is not
--   (FeedNotices' docstring), so no window source here has one.
-- A source int_sources__publication no longer lets publish carries nothing:
-- the finals join it, as they do every row. The gate's read checks do not
-- apply, on purpose: a source whose read broke this hour is exactly the case
-- where its last good rows are the honest answer (phase D's "a club the gate
-- holds keeps its last good rows").
--
-- Only the club notices' columns are carried (stg_row_history__closures says
-- why), every one of them, so a carried row is the last version's content
-- exactly, its `_row_hash` is unchanged and the snapshot opens no version
-- for it. The two dates are read out of the saved row (`row_json`), as
-- int_closures__held_carried reads every column: a feed item's `starts_on`
-- is its published date, and dropping it moved the row's `_changed_at` and
-- took the "from" date off notices.json (reproduced on the fixtures'
-- gatc_alerts `?p=751` in the review of PR #1805 — dlt → dbt re-platform as
-- one go/no-go change, 2026-10-05; with both dates carried, the same item
-- leaving the feed opened no version).
-- Empty on a cold start, when there is no history to carry.
with closures_history as (
    select
        'closures' as mart,
        closure_id as notice_id,
        try_cast(json_extract_string(row_json, '$.starts_on') as date)
            as starts_on,
        try_cast(json_extract_string(row_json, '$.ends_on') as date)
            as ends_on,
        * exclude (
            closure_id, history_row_key, dbt_scd_id, dbt_valid_to, row_json
        )
    from {{ ref('stg_row_history__closures') }}
    where dbt_valid_to is null
),

warnings_history as (
    select
        'warnings' as mart,
        warning_id as notice_id,
        try_cast(json_extract_string(row_json, '$.starts_on') as date)
            as starts_on,
        try_cast(json_extract_string(row_json, '$.ends_on') as date)
            as ends_on,
        * exclude (
            warning_id,
            warning_kind,
            history_row_key,
            dbt_scd_id,
            dbt_valid_to,
            row_json
        )
    from {{ ref('stg_row_history__warnings') }}
    where dbt_valid_to is null and warning_kind = 'org_notice'
),

held as (
    select * from closures_history
    union all by name
    select * from warnings_history
),

windows as (
    select distinct source_key
    from {{ ref('notice_readers') }}
    where listing = 'window'
),

-- Every notice this build read, held back or not: one it read is not absent.
present as (
    select notice_id from {{ ref('int_closures__unioned') }}
    union distinct
    select notice_id from {{ ref('int_warnings__unioned') }}
),

marks as (
    select notice_id
    from {{ ref('notice_marks') }}
    where mark = 'lifted'
),

carried as (
    select
        held.*,
        {{ notice_has_ended('held.ends_on', notice_build_date()) }} as has_ended
    from held
    inner join windows on held.source_key = windows.source_key
    left join present on held.notice_id = present.notice_id
    left join marks on held.notice_id = marks.notice_id
    where present.notice_id is null and marks.notice_id is null
)

-- A carried closure whose own end has passed since it was read no longer
-- closes the trail: it moves to the warnings mart with `obstructs_trail`
-- null and `not_reviewed`, as int_closures__held_carried judges a held one.
select
    case when has_ended then 'warnings' else mart end as mart,
    case when has_ended then null else obstructs_trail end as obstructs_trail,
    case when has_ended then 'not_reviewed' else review_state end
        as review_state,
    * exclude (mart, obstructs_trail, review_state, has_ended)
from carried

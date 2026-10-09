{{ config(severity='warn') }}
-- Decision 128 (the maintainer's poll of 2026-10-09): a section of a source
-- seeds/notice_confirming_pages.csv names draws only while a person's match
-- of it to an item on its page stands, and its card then carries that
-- page's date and link (pub_conditions_notices' `matched_page`). So every
-- row such a source has in the closures or warnings mart, read this build
-- or carried, must have a standing match in int_closures__page_matches,
-- matched to the row's own raw key. int_closures__club_notices' rule 7 and
-- int_closures__held_carried make that so; this returns each row that
-- slipped past them, which would reach a phone as a bare "Closed" with no
-- date and no link, the card decision 128 turned down.
--
-- AT WARN, as decision 81 set the per-row checks: a failed test here would
-- otherwise skip every writer and publish no one's file over one source's
-- row, the outcome that decision rejected. The log names the rows.
with confirming as (
    select distinct source_key
    from {{ ref('notice_confirming_pages') }}
),

standing as (
    select
        notice_id,
        source_row_key
    from {{ ref('int_closures__page_matches') }}
    where held_because is null
),

mart_rows as (
    select
        closure_id as notice_id,
        source_key,
        source_row_key,
        'closures' as mart
    from {{ ref('closures', v=1) }}
    union all
    select
        warning_id as notice_id,
        source_key,
        source_row_key,
        'warnings' as mart
    from {{ ref('warnings', v=1) }}
)

select
    mart_rows.mart,
    mart_rows.notice_id,
    mart_rows.source_key
from mart_rows
inner join confirming on mart_rows.source_key = confirming.source_key
left join standing
    on
        mart_rows.notice_id = standing.notice_id
        and mart_rows.source_row_key = standing.source_row_key
where standing.notice_id is null

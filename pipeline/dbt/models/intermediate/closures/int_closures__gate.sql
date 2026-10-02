{{ config(materialized='table') }}
-- The per-source gate (pipeline/ELT.md, "A whole-file gate becomes a
-- per-source gate"): one row per notice source, `rows_invalid` and
-- `passed`. Today one bad ATC row publishes no ATC updates
-- (export_atc_updates.py, CL05) and leaves every other artifact alone, and a
-- failing test on the shared mart would hold back OurHike's verified closures
-- too. So the marts keep only the sources that pass here, and a writer
-- refuses to write a held source's file, which leaves its last good file on
-- the phone (pub_conditions_atc_updates, pub_conditions_nynjtc_alerts,
-- pub_conditions_closures).
--
-- WHAT HOLDS A SOURCE BACK, each as today's code holds it back:
--   atc_trail_updates     any row problem (CL01-CL06), or a file nobody
--                         reviewed (no `reviewed_at`), or a file with no rows,
--                         from which no review date can be read: an empty
--                         reviewed file publishes `atc_updates: []` today, and
--                         the warehouse cannot tell it from an unreviewed one
--                         (the review rides each row's `_file`)
--   nynjtc_trail_alerts   any post that cannot be read, or no posts at all,
--                         which fetch_nynjtc_alerts.py reads as a broken parse
--   ourhike_closures      a row that is not moderator-verified (CL15)
--   oprhp_trail_closures  nothing: an empty layer is a good week
-- `held_because` says which, for the job log, and is null for a source that
-- passes. Its test warns rather than fails, because failing the build would
-- hold back every source for one.
--
-- THE SOURCE LIST IS TYPED BY HAND, one row per branch of
-- int_closures__unioned, so a source with no rows today still gets its row
-- and its answer. A branch added there without a row here has no gate row,
-- and the marts' inner join drops it: held back, never published unchecked.
with notices as (
    select * from {{ ref('int_closures__unioned') }}
),

atc_review as (
    select
        count(*) as rows_total,
        coalesce(bool_and(is_reviewed), false) as is_reviewed
    from {{ ref('int_closures__atc_checked') }}
),

gated_sources as (
    select
        gated.source_key,
        gated.club
    from (
        values
        ('atc_trail_updates', 'atc'),
        ('nynjtc_trail_alerts', 'nynjtc'),
        ('oprhp_trail_closures', 'nysparks'),
        ('ourhike_closures', 'ourhike')
    ) as gated (source_key, club)
),

counts as (
    select
        source_key,
        count(*) as rows_total,
        count(*) filter (where len(problems) > 0) as rows_invalid
    from notices
    group by source_key
),

judged as (
    select
        gated_sources.source_key,
        gated_sources.club,
        coalesce(counts.rows_total, 0) as rows_total,
        coalesce(counts.rows_invalid, 0) as rows_invalid,
        case
            when
                gated_sources.source_key = 'atc_trail_updates'
                and atc_review.rows_total = 0
                then
                    'reference/atc_updates.json has no rows, so no review date '
                    || 'to read: an unreviewed file publishes nothing'
            when
                gated_sources.source_key = 'atc_trail_updates'
                and not atc_review.is_reviewed
                then
                    'reference/atc_updates.json has no reviewed_at, so nobody '
                    || 'has checked it against ATC''s page'
            when
                gated_sources.source_key = 'nynjtc_trail_alerts'
                and coalesce(counts.rows_total, 0) = 0
                then
                    'NYNJTC''s Trail Alerts category has no posts at all, '
                    || 'which means the parse broke'
            when coalesce(counts.rows_invalid, 0) > 0
                then
                    counts.rows_invalid || ' of ' || counts.rows_total
                    || ' rows cannot publish, and a partial set of safety '
                    || 'notices is worse than none'
        end as held_because
    from gated_sources
    cross join atc_review
    left join counts on gated_sources.source_key = counts.source_key
)

select
    source_key,
    club,
    rows_total,
    rows_invalid,
    held_because is null as passed,
    held_because
from judged

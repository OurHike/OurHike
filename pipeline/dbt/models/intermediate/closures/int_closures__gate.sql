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
--   atc_trail_updates     a file nobody reviewed (no `reviewed_at`, read
--                         from the file landed whole, base_atc__atc_updates),
--                         a file whose `updates` is not a list, then any row
--                         problem (CL01-CL06), in export_atc_updates.py's
--                         order; and a file whose two landings disagree on
--                         how many rows it has. An empty reviewed file
--                         passes, and publishes `atc_updates: []` as today
--   nynjtc_trail_alerts   any post that cannot be read, or no posts at all,
--                         which fetch_nynjtc_alerts.py reads as a broken parse
--   ourhike_closures      a row that is not moderator-verified (CL15)
--   oprhp_trail_closures  nothing: an empty layer is a good week
-- and, before any of those, a source int_sources__publication does not let
-- publish, or has no row for. The marts join int_sources__publication
-- themselves; it is here as well so that a writer, which cannot tell a
-- source with nothing to report from one whose rows the marts left out,
-- reads one answer per source and refuses rather than write `[]`.
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

publication as (
    select * from {{ ref('int_sources__publication') }}
),

atc_rows as (
    select count(*) as rows_total
    from {{ ref('int_closures__atc_checked') }}
),

atc_document_fields as (
    select
        json_extract(document_json, '$.reviewed_at') as reviewed_at_json,
        json_extract(document_json, '$.updates') as updates_json
    from {{ ref('base_atc__atc_updates') }}
),

-- lib/atc_updates.py's is_reviewed() and file_problems()'s first check, on
-- the document. `reviewed_at` is published as written, so it is kept as
-- written here.
atc_document as (
    select
        count(*) as documents,
        max(
            case
                when json_type(reviewed_at_json) = 'VARCHAR'
                    then json_extract_string(reviewed_at_json, '$')
            end
        ) as reviewed_at,
        coalesce(
            bool_and(
                json_type(reviewed_at_json) = 'VARCHAR'
                and {{ python_strip(
                    "json_extract_string(reviewed_at_json, '$')"
                ) }} != ''
            ),
            false
        ) as is_reviewed,
        max(
            case
                when json_type(updates_json) = 'ARRAY'
                    then json_array_length(updates_json)
            end
        ) as updates_listed
    from atc_document_fields
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
        coalesce(publication.may_publish, false) as may_publish,
        case
            when gated_sources.source_key = 'atc_trail_updates'
                then atc_document.reviewed_at
        end as reviewed_at,
        -- The one hold that is not a failure: held_because's unreviewed
        -- branch, reached only past the publication and landing checks
        -- above it. export_atc_updates.py writes nothing and exits 0 for it,
        -- so pub_conditions_atc_updates writes nothing and succeeds.
        coalesce(
            gated_sources.source_key = 'atc_trail_updates'
            and publication.may_publish
            and atc_document.documents = 1
            and not atc_document.is_reviewed,
            false
        ) as awaiting_review,
        case
            when publication.source_key is null
                then
                    'int_sources__publication has no row for '
                    || gated_sources.source_key
                    || ', so nothing says it may publish'
            when not publication.may_publish
                then
                    'int_sources__publication holds '
                    || gated_sources.source_key || ' back ('
                    || coalesce(publication.publication_rule, 'no rule') || ')'
            when
                gated_sources.source_key = 'atc_trail_updates'
                and atc_document.documents != 1
                then
                    'reference/atc_updates.json did not land whole, so its '
                    || 'review cannot be read'
            when
                gated_sources.source_key = 'atc_trail_updates'
                and not atc_document.is_reviewed
                then
                    'reference/atc_updates.json has no reviewed_at, so nobody '
                    || 'has checked it against ATC''s page'
            when
                gated_sources.source_key = 'atc_trail_updates'
                and atc_document.updates_listed is null
                then '`updates` is missing or is not a list'
            when
                gated_sources.source_key = 'atc_trail_updates'
                and atc_document.updates_listed != atc_rows.rows_total
                then
                    'reference/atc_updates.json lists '
                    || atc_document.updates_listed || ' updates and '
                    || atc_rows.rows_total || ' landed as rows, so the two '
                    || 'landings are of different files'
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
    cross join atc_rows
    cross join atc_document
    left join counts on gated_sources.source_key = counts.source_key
    left join publication
        on gated_sources.source_key = publication.source_key
)

select
    source_key,
    club,
    rows_total,
    rows_invalid,
    may_publish,
    reviewed_at,
    held_because is null as passed,
    held_because,
    awaiting_review
from judged

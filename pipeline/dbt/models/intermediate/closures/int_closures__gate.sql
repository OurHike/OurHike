{{ config(materialized='table') }}
-- The per-source gate (pipeline/ELT.md, "A whole-file gate becomes a
-- per-source gate"): one row per source a conditions file is written from,
-- with `passed` and, where it did not, `held_because`. The marts keep only
-- the notice sources that pass. Each pub_conditions_* writer selects no row
-- for a source held here, so phone_file's `when_empty: keep_last_file` writes
-- nothing and the phone keeps its last file, with its true age, while every
-- other file is written. publish.py reads `held_because` after the upload and
-- fails the run for each held file (its writer's `meta.gate` names the row).
-- A table, so that read needs no spatial extension.
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
--   ourhike_closures      a row that is not moderator-verified (CL15), or
--                         whose mile or coordinate is not a finite number
--   oprhp_trail_closures  nothing: an empty layer is a good week
--   ourhike_reports       a coordinate or mile that is not a finite number
--   nws_alerts            no alert landed, so nothing says when NWS was asked
--   reference/work_projects.json
--                         a file that did not land as one row, a file nobody
--                         reviewed, then any of file_problems()'s problems
-- and, before any of those, a source int_sources__publication does not let
-- publish, or has no row for. A non-finite number is held because
-- write_document()'s allow_nan=False refuses it: JSON.parse on a phone
-- rejects the whole document over one NaN (lib/strict_json.py, #658).
-- `awaiting_review` marks the two holds that are not failures: an unreviewed
-- ATC or work-projects file, for which the Python writes nothing and exits 0.
-- The test below warns rather than fails, because failing the build would
-- hold back every source for one.
--
-- THE SOURCE LIST IS TYPED BY HAND, one row per branch of
-- int_closures__unioned and one per other conditions file, so a source with
-- no rows today still gets its answer. A branch added there without a row
-- here has no gate row, and the marts' inner join drops it: held back, never
-- published unchecked.
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

-- PUBLIC_REPORTS_SQL's predicate, as pub_conditions_reports applies it.
ourhike_reports as (
    select
        count(*) as rows_total,
        count(*) filter (
            where not (
                coalesce(isfinite(lat), true)
                and coalesce(isfinite(lon), true)
                and coalesce(isfinite(mile), true)
            )
        ) as rows_not_finite
    from {{ ref('base_ourhike__reports') }}
    where
        report_status in ('verified', 'resolved')
        and visibility = 'public'
),

nws_alerts as (
    select count(*) as rows_total
    from {{ ref('base_nws__alerts') }}
),

work_projects_rows as (
    select * from {{ ref('int_closures__work_projects_checked') }}
),

-- The file's own row (no position): its review, as is_reviewed() reads it;
-- and file_problems()'s list, in its order: the file's own, each repeated
-- id in row order, then each row's own.
work_projects as (
    select
        count(*) filter (where row_position is null) as documents,
        count(*) filter (where row_position is not null) as rows_total,
        coalesce(
            bool_and(is_reviewed) filter (where row_position is null), false
        ) as is_reviewed,
        list_concat(
            flatten(
                coalesce(
                    list(row_problems) filter (where row_position is null), []
                )
            ),
            flatten(
                coalesce(
                    list(duplicate_problems order by row_position)
                    filter (where row_position is not null),
                    []
                )
            ),
            flatten(
                coalesce(
                    list(row_problems order by row_position)
                    filter (where row_position is not null),
                    []
                )
            )
        ) as file_problems
    from work_projects_rows
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
        ('ourhike_closures', 'ourhike'),
        ('ourhike_reports', 'ourhike'),
        ('nws_alerts', 'nws'),
        ('reference/work_projects.json', 'ourhike')
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
        case gated_sources.source_key
            when 'ourhike_reports' then ourhike_reports.rows_total
            when 'nws_alerts' then nws_alerts.rows_total
            when 'reference/work_projects.json' then work_projects.rows_total
            else coalesce(counts.rows_total, 0)
        end as rows_total,
        case gated_sources.source_key
            when 'ourhike_reports' then ourhike_reports.rows_not_finite
            else coalesce(counts.rows_invalid, 0)
        end as rows_invalid,
        coalesce(publication.may_publish, false) as may_publish,
        case
            when gated_sources.source_key = 'atc_trail_updates'
                then atc_document.reviewed_at
        end as reviewed_at,
        -- The two holds that are not failures, each reached only past the
        -- publication and landing checks above it in held_because.
        coalesce(
            (
                gated_sources.source_key = 'atc_trail_updates'
                and publication.may_publish
                and atc_document.documents = 1
                and not atc_document.is_reviewed
            )
            or (
                gated_sources.source_key = 'reference/work_projects.json'
                and publication.may_publish
                and work_projects.documents = 1
                and not work_projects.is_reviewed
            ),
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
            when
                gated_sources.source_key = 'ourhike_reports'
                and ourhike_reports.rows_not_finite > 0
                then
                    ourhike_reports.rows_not_finite
                    || ' row(s) carry a coordinate or a mile that is not a '
                    || 'finite number, and JSON.parse on a phone rejects the '
                    || 'whole document'
            when
                gated_sources.source_key = 'nws_alerts'
                and nws_alerts.rows_total = 0
                then 'no NWS alert landed, so nothing says when NWS was asked'
            when
                gated_sources.source_key = 'reference/work_projects.json'
                and work_projects.documents != 1
                then
                    'reference/work_projects.json landed as '
                    || work_projects.documents
                    || ' rows, so its review cannot be read'
            when
                gated_sources.source_key = 'reference/work_projects.json'
                and not work_projects.is_reviewed
                then 'nobody has reviewed reference/work_projects.json'
            when
                gated_sources.source_key = 'reference/work_projects.json'
                and len(work_projects.file_problems) > 0
                then
                    len(work_projects.file_problems) || ' problem(s) in '
                    || 'reference/work_projects.json, the first: '
                    || work_projects.file_problems[1]
        end as held_because
    from gated_sources
    cross join atc_rows
    cross join atc_document
    cross join ourhike_reports
    cross join nws_alerts
    cross join work_projects
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

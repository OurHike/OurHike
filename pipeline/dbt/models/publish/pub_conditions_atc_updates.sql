{{ config(format='json', location='conditions_atc_updates.json') }}
-- conditions/atc_updates.json, ATC's own Trail Updates (#460), in the shape
-- export_atc_updates.py's build_document() writes: `generated_at`, the
-- reviewed file's `reviewed_at`, and every reviewed row in the file's order,
-- each as lib/atc_updates.py's published_rows() writes it.
--
-- WHICH ROWS: ATC's rows in the closures mart and in the warnings mart.
-- Decision 7 splits them by obstructs_trail, and this file has always held
-- both halves. Each row's JSON is int_closures__atc_checked's
-- published_row, the reviewer's own values, read by the mart row's key.
--
-- NOTHING IS WRITTEN for a file int_closures__gate holds back, whether for
-- its rows or because int_sources__publication holds ATC back: the model
-- fails with the gate's reason before the copy, so the last good file stays
-- on the phone, as export_atc_updates.py writes nothing for an unreviewed
-- file or a bad row (CL05). One difference: export_atc_updates.py exits 0
-- for an unreviewed file, on purpose ("a red X on a job that is behaving
-- correctly is how a real failure gets missed later"), and this model fails
-- for one, because phone_file has no way to write nothing and succeed.
--
-- NOT HERE YET: the automatic rows export_atc_updates.py appends from
-- fetch_atc_updates.py's scrape (CL07-CL10). No extract lands the scrape, so
-- this writes the reviewed rows only.
--
-- `generated_at` is dbt's run_started_at, stamped as _stamp_utc() stamps:
-- one clock for every writer in a run.
with atc_rows as (
    select
        source_row_key,
        list_position
    from {{ ref('closures') }}
    where source_key = 'atc_trail_updates'
    union all
    select
        source_row_key,
        list_position
    from {{ ref('warnings') }}
    where source_key = 'atc_trail_updates' and warning_kind = 'org_notice'
),

checked as (
    select * from {{ ref('int_closures__atc_checked') }}
),

gate as (
    select * from {{ ref('int_closures__gate') }}
    where source_key = 'atc_trail_updates'
),

published as (
    select
        coalesce(
            list(checked.published_row order by atc_rows.list_position), []
        ) as atc_updates
    from atc_rows
    inner join checked
        on atc_rows.source_row_key = checked.atc_update_row_key
),

review as (
    select max(reviewed_at) as reviewed_at from checked
),

-- One row whatever the gate holds, so a missing gate or registry row fails
-- the write rather than writing no document at all.
judged as (
    select
        published.atc_updates,
        review.reviewed_at,
        coalesce(gate.passed, false) as passed,
        coalesce(
            gate.held_because,
            'int_closures__gate has no row for atc_trail_updates'
        ) as held_because
    from published
    cross join review
    left join gate on true
)

select
    case
        when passed
            then {{ python_run_stamp() }}
        else error(
            'conditions/atc_updates.json is not written: ' || held_because
        )
    end as generated_at,
    reviewed_at,
    atc_updates
from judged

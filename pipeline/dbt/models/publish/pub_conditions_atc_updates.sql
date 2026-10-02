{{ config(
    format='json',
    location='conditions_atc_updates.json',
    meta={'when_empty': 'keep_last_file'},
) }}
-- conditions/atc_updates.json, ATC's own Trail Updates (#460), in the shape
-- export_atc_updates.py's build_document() writes: `generated_at`, the
-- reviewed file's `reviewed_at`, every reviewed row in the file's order, each
-- as lib/atc_updates.py's published_rows() writes it, and then every update
-- ATC posted since the review that publishes without a person (#963,
-- CL07-CL10), in slug order, each as auto_row() writes it.
--
-- WHICH ROWS: ATC's rows in the closures mart and in the warnings mart.
-- Decision 7 splits them by obstructs_trail, and this file has always held
-- both halves; an automatic row's obstructs_trail is forced false, so every
-- one is in the warnings mart (review_state `auto`). Each row's JSON is the
-- published_row of int_closures__atc_checked (the reviewer's own values) or
-- of int_closures__atc_automatic, read by the mart row's key. Both kinds
-- share one payload, told apart by each row's `review_state`, so a phone
-- cannot read half of it (export_atc_updates.py's build_document()).
--
-- NOTHING IS WRITTEN for a file int_closures__gate holds back, so the last
-- good file stays on the phone, as export_atc_updates.py writes nothing for
-- an unreviewed file or a bad row (CL05), and the run ends as today's does:
-- - a file nobody has reviewed yet selects no row, and phone_file's
--   `when_empty: keep_last_file` writes nothing and succeeds, as the Python
--   exits 0 on purpose ("a red X on a job that is behaving correctly is how
--   a real failure gets missed later");
-- - every other hold, for its rows or because int_sources__publication holds
--   ATC back, fails with the gate's reason before the copy, as the Python
--   exits 1 for a bad row.
--
-- `generated_at` is dbt's run_started_at, stamped as _stamp_utc() stamps:
-- one clock for every writer in a run.
with atc_rows as (
    select
        source_row_key,
        review_state = 'auto' as automatic,
        list_position
    from {{ ref('closures', v=1) }}
    where source_key = 'atc_trail_updates'
    union all
    select
        source_row_key,
        review_state = 'auto' as automatic,
        list_position
    from {{ ref('warnings', v=1) }}
    where source_key = 'atc_trail_updates' and warning_kind = 'org_notice'
),

checked as (
    select
        atc_update_row_key as row_key,
        published_row
    from {{ ref('int_closures__atc_checked') }}
    union all
    select
        atc_trail_update_page_key as row_key,
        published_row
    from {{ ref('int_closures__atc_automatic') }}
    where publishes
),

gate as (
    select * from {{ ref('int_closures__gate') }}
    where source_key = 'atc_trail_updates'
),

-- The reviewed rows first, in the file's order, then the automatic ones in
-- slug order: [*published_rows(document), *automatic].
published as (
    select
        coalesce(
            list(
                checked.published_row
                order by atc_rows.automatic, atc_rows.list_position
            ),
            []
        ) as atc_updates
    from atc_rows
    inner join checked
        on atc_rows.source_row_key = checked.row_key
),

-- One row whatever the gate holds, so a missing gate or registry row fails
-- the write rather than writing no document at all.
judged as (
    select
        published.atc_updates,
        gate.reviewed_at,
        coalesce(gate.passed, false) as passed,
        coalesce(
            gate.held_because,
            'int_closures__gate has no row for atc_trail_updates'
        ) as held_because,
        coalesce(gate.awaiting_review, false) as awaiting_review
    from published
    left join gate on gate.source_key = 'atc_trail_updates'
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
where not awaiting_review

{{ config(
    format='json',
    location='conditions_work_projects.json',
    meta={'when_empty': 'keep_last_file', 'gate': 'reference/work_projects.json'},
) }}
-- conditions/work_projects.json, the club workdays a hiker can see and join
-- (#760), in the shape export_work_projects.py's main() writes:
-- `generated_at`, the reviewed file's `reviewed_at` as written, and
-- `work_projects`, every row of reference/work_projects.json in the file's
-- order, each as lib/work_projects.py's published_rows() writes it
-- (int_closures__work_projects_checked, CL17). No mart owns work projects
-- (ELT.md, "What reaches a phone from no mart").
--
-- REWRITTEN WHOLE EVERY RUN (CL18): a cancelled or removed workday clears
-- with the next build, because the extract replaces the file's one row
-- whenever its bytes change and this writes the file from that row alone.
--
-- NO ROW, SO NO FILE, while int_closures__gate holds the file back
-- (`meta.gate`), and the phone keeps its last file:
-- - nobody has reviewed it (lib/work_projects.py's is_reviewed()), for which
--   export_work_projects.py exits 0, so publish.py does not fail the run;
-- - it has any problem, its own or a row's, or did not land as exactly one
--   row, for which export_work_projects.py exits 1, so publish.py fails the
--   run after publishing the rest.
--
-- `generated_at` is dbt's run_started_at, stamped as _stamp_utc() stamps:
-- one clock for every writer in a run.
with checked as (
    select * from {{ ref('int_closures__work_projects_checked') }}
),

gate as (
    select * from {{ ref('int_closures__gate') }}
    where source_key = 'reference/work_projects.json'
),

-- The file's review as written, from its own row (no position), and its
-- rows in file order.
published as (
    select
        max(reviewed_at) filter (where row_position is null) as reviewed_at,
        coalesce(
            list(published_row order by row_position)
            filter (where row_position is not null),
            []
        ) as work_projects
    from checked
)

select
    {{ python_run_stamp() }} as generated_at,
    published.reviewed_at,
    published.work_projects
from published
inner join gate on gate.source_key = 'reference/work_projects.json'
where gate.passed

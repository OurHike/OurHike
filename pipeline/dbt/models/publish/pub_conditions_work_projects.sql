{{ config(
    format='json',
    location='conditions_work_projects.json',
    meta={'when_empty': 'keep_last_file'},
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
-- NOTHING IS WRITTEN, and the last good file stays on the phone, when:
-- - nobody has reviewed the file (lib/work_projects.py's is_reviewed()): no
--   row is selected, and phone_file's `when_empty: keep_last_file` writes
--   nothing and succeeds, as export_work_projects.py exits 0 for it;
-- - the file has any problem, its own or a row's: this fails with the first
--   of them, as export_work_projects.py prints each and exits 1;
-- - the file did not land as exactly one row, so its review cannot be read.
--
-- `generated_at` is dbt's run_started_at, stamped as _stamp_utc() stamps:
-- one clock for every writer in a run.
with checked as (
    select * from {{ ref('int_closures__work_projects_checked') }}
),

-- The file's own row: its review, read as is_reviewed() reads it.
judged_review as (
    select
        count(*) as documents,
        max(reviewed_at) as reviewed_at,
        coalesce(bool_and(is_reviewed), false) as is_reviewed
    from checked
    where row_position is null
),

-- file_problems()'s list, in its order: the file's own (on the one row with
-- no position), each repeated id in row order, then each row's own.
problems as (
    select
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
        ) as file_problems,
        coalesce(
            list(published_row order by row_position)
            filter (where row_position is not null),
            []
        ) as work_projects
    from checked
),

judged as (
    select
        judged_review.documents,
        judged_review.reviewed_at,
        judged_review.is_reviewed,
        problems.file_problems,
        problems.work_projects
    from judged_review
    cross join problems
)

select
    case
        when documents != 1
            then error(
                'conditions/work_projects.json is not written: '
                || 'reference/work_projects.json landed as ' || documents
                || ' rows, so its review cannot be read'
            )
        when len(file_problems) > 0
            then error(
                'conditions/work_projects.json is not written: '
                || len(file_problems) || ' problem(s) in '
                || 'reference/work_projects.json, the first: '
                || file_problems[1]
            )
        else {{ python_run_stamp() }}
    end as generated_at,
    reviewed_at,
    work_projects
from judged
where is_reviewed or documents != 1

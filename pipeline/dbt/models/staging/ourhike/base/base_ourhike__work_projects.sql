-- reference/work_projects.json whole
-- (extract/_shared/ourhike/work_projects.py), as its one row, keyed
-- (decision 40), with nothing filtered. The file is
-- landed whole, `_README` aside, rather than one row per row of `rows`,
-- because `rows` is empty today (maintainer decision 2026-08-20, on #760), so
-- a row-per-row table would have no columns at all, and because the review,
-- `reviewed_at`, and the retired `ua_sample_rows` key are facts about the
-- file that int_closures__work_projects_checked reads whatever `rows` holds.
--
-- Key: the file and its landed path, which together are the row.
with source as (
    select * from {{ source('ourhike', 'raw_ourhike__work_projects') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'reference/work_projects.json'",
            '_path',
        ]) }} as work_projects_document_key,
        _path as file_path,
        cast(row_json as json) as document_json,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='work_projects_document_key', order_by='_dlt_id'
) }}

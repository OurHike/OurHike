-- reference/atc_updates.json (extract/atc/closures.py): ATC's Trail Updates
-- as a person reviewed them, one row per row of the file, keyed (decision
-- 40), with nothing filtered and nothing joined. Each row is still the JSON
-- its reviewer wrote, and the file's own fields (`reviewed_at`,
-- `source_marker`) ride every row: reading both is the gate's work
-- (int_closures__atc_checked), because a field's JSON type is one of the
-- things lib/atc_updates.py checks.
--
-- Key: the file and the row's place in it, unique by construction. ELT.md's
-- key table records ATC's slug, `atc_id`, as unique on all 35 rows
-- (measured 2026-10-01), but whether it is unique is a check the gate makes
-- (CL04), and a dedupe on it would quietly publish one of two rows that
-- lib/atc_updates.py refuses as "appears more than once".
with source as (
    select * from {{ source('atc', 'raw_atc__atc_trail_updates') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'reference/atc_updates.json'",
            '_row',
        ]) }} as atc_update_row_key,
        _row as file_row,
        cast(row_json as json) as atc_update,
        cast(_file as json) as reviewed_file,
        _path as file_path,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='atc_update_row_key', order_by='_dlt_id'
) }}

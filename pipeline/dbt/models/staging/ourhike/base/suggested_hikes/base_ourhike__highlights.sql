-- reference/highlights.json (_shared/ourhike/highlights.py): every row of
-- the curated list, keyed (decision 40), with nothing filtered and nothing
-- joined. Each row is still the JSON its reviewer wrote: resolving it is
-- int_suggested_hikes__highlights' work, because a field's JSON type is one
-- of the things lib/highlights.py's resolve() checks.
--
-- Key: the file and the row's place in it, unique by construction: `id` is
-- what the resolution checks for, so it cannot be the key.
with source as (
    select * from {{ source('ourhike', 'raw_ourhike__highlights') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'reference/highlights.json'",
            '_row',
        ]) }} as highlight_row_key,
        _row as file_row,
        cast(row_json as json) as highlight,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='highlight_row_key', order_by='_dlt_id'
) }}

-- reference/atc_updates.json whole (extract/atc/closures.py's second
-- resource), as its one row, keyed (decision 40), with nothing filtered.
-- The review is the file's, not a row's: lib/atc_updates.py's is_reviewed()
-- reads the document, and an empty reviewed file publishes `atc_updates: []`,
-- so int_closures__gate reads the review here, where it exists however many
-- rows `updates` holds.
--
-- Key: the file and its landed path, which together are the row.
with source as (
    select * from {{ source('atc', 'raw_atc__atc_updates') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'reference/atc_updates.json'",
            '_path',
        ]) }} as atc_updates_document_key,
        _path as file_path,
        cast(row_json as json) as document_json,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='atc_updates_document_key', order_by='_dlt_id'
) }}

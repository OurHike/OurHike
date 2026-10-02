-- reference/blaze_mapping.json, landed by _shared/ourhike/: the reviewed
-- file as its one row, keyed (decision 40), with nothing filtered and
-- nothing joined. The document is still the JSON a person reviewed in;
-- staging models read its parts.
--
-- Key: the file and its landed path, which together are the row.
with source as (
    select * from {{ source('ourhike', 'raw_ourhike__blaze_mapping') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'reference/blaze_mapping.json'",
            '_path',
        ]) }} as blaze_mapping_document_key,
        _path as file_path,
        cast(row_json as json) as document_json,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='blaze_mapping_document_key', order_by='_dlt_id'
) }}

-- sources.json (_shared/registry/): the registry, as its one row, keyed
-- (decision 40), with nothing filtered and nothing joined. The document is
-- still the JSON a person reviewed in; the staging models read its parts.
--
-- Key: the file and its landed path, which together are the row.
with source as (
    select * from {{ source('registry', 'raw_registry__sources') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'sources.json'",
            '_path',
        ]) }} as registry_document_key,
        _path as file_path,
        cast(row_json as json) as document_json,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='registry_document_key', order_by='_dlt_id'
) }}

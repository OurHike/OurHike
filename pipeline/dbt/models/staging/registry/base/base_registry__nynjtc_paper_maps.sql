-- reference/nynjtc_paper_maps.json (_shared/registry/): NYNJTC's paper-map
-- table, as its one row, keyed (decision 40), with nothing filtered and
-- nothing joined. The document is still the JSON a person reviewed in; the
-- staging models read its parts.
--
-- Key: the file and its landed path, which together are the row.
with source as (
    select * from {{ source('registry', 'raw_registry__nynjtc_paper_maps') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'reference/nynjtc_paper_maps.json'",
            '_path',
        ]) }} as paper_map_table_key,
        _path as file_path,
        cast(row_json as json) as document_json,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='paper_map_table_key', order_by='_dlt_id'
) }}

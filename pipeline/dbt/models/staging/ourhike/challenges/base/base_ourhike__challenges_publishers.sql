-- reference/challenges/publishers.json whole
-- (extract/_shared/ourhike/challenge_publishers.py), as its one row, keyed
-- (decision 40), with nothing filtered. Its `publishers` are read and checked
-- by int_challenges__publishers, as export_challenges.py's load_publishers()
-- and publisher_scope() read them.
--
-- Key: the file and its landed path, which together are the row.
with source as (
    select * from {{ source('ourhike', 'raw_ourhike__challenges_publishers') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'reference/challenges/publishers.json'",
            '_path',
        ]) }} as publishers_document_key,
        _path as file_path,
        cast(row_json as json) as file_json,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='publishers_document_key', order_by='_dlt_id'
) }}

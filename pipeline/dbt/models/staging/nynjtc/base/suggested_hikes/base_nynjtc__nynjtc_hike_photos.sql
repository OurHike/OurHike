-- reference/nynjtc_hike_photos.json (extract/nynjtc/photos.py): every row of
-- the person-confirmed hike-to-photograph join, keyed (decision 40), with
-- nothing filtered and nothing joined. Each row is still the JSON its
-- reviewer wrote: which rows confirm a photograph is the join's work
-- (int_suggested_hikes__photos), because a field's own truth is what it
-- checks.
--
-- Key: the file and the row's place in it, unique by construction, since a
-- reviewed file has no other id every row is sure to carry.
with source as (
    select * from {{ source('nynjtc', 'raw_nynjtc__nynjtc_hike_photos') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'reference/nynjtc_hike_photos.json'",
            '_row',
        ]) }} as photo_row_key,
        _row as file_row,
        cast(row_json as json) as photo,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='photo_row_key', order_by='_dlt_id'
) }}

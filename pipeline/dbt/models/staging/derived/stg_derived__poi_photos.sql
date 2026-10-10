-- The photo manifests export_poi.py attaches: step_poi_photos's table
-- (pipeline/step_poi_photos.py), staged like any table a source lands, one
-- row per found photo. Nothing is gated here: the face screen's gate and the
-- attachment are int_points_of_interest__photos'.
with source as (
    select * from {{ source('derived', 'poi_photos') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'poi_photos'",
            'source',
            'poi_id',
            'photo_index',
        ]) }} as poi_photo_key,
        source,
        poi_id,
        photo_index,
        digest,
        page_url,
        author,
        license,
        taken,
        screened,
        flagged,
        decision,
        photo,
        _loaded_at
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='poi_photo_key', order_by='photo_index'
) }}

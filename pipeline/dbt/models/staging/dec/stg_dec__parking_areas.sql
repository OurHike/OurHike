-- DEC's parking areas, same shape and reasoning as stg_dec__lean_tos.
-- 1,852 rows, counted live 2026-08-27.
--
-- NO SEASONAL ACCESS COLUMN, and that absence is measured rather than
-- assumed: sources.json read one sampled row carrying 'SEASONALLY OPEN MAY 1
-- TO SEPT 30' in free-text NOTES, so seasonality exists in DEC's data as
-- PROSE and not as a field. A model that invented an `open_seasonally`
-- column would be answering a question DEC has not answered.
with source as (
    select * from {{ source('dec', 'raw_dec__dec_parking_areas') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'dec_parking_areas'",
            'asset_uid',
            geometry_key('geom'),
        ]) }} as poi_key,
        'dec_parking_areas' as source,
        cast(objectid as varchar) as source_id,
        name,
        'parking' as poi_type,
        'high' as confidence,
        publicuse as public_use,
        st_x(geom) as longitude,
        st_y(geom) as latitude,
        _loaded_at as loaded_at
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='poi_key', order_by='source_id'
) }}
